# Copyright (c) 2013 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import sys
import tarfile
import shutil
import tempfile
import hashlib
from glob import glob
from metadataclient.common.exceptions import CommunicationError
from muranoconductor import config
from metadataclient.v1.client import Client
import os
from keystoneclient.v2_0 import client as ksclient
from keystoneclient.exceptions import EndpointNotFound

from openstack.common import log as logging

CHUNK_SIZE = 1 << 20  # 1MB

log = logging.getLogger(__name__)
CONF = config.CONF


class MetadataException(BaseException):
    # Inherited not from Exception in purpose:
    # On this exception ack message would not be sent
    pass


def _unpack_data_archive(task_id, hash):
    archive_name = hash + '.tar.gz'
    if not tarfile.is_tarfile(archive_name):
        raise MetadataException('Received invalid file {0} from Metadata '
                                'Repository'.format(hash))
    dst_dir = task_id
    if not os.path.exists(dst_dir):
        os.mkdir(dst_dir)
    tar = tarfile.open(archive_name, 'r:gz')
    try:
        tar.extractall(path=dst_dir)
    finally:
        tar.close()
    return dst_dir


def get_endpoint(token_id, tenant_id):
    endpoint = CONF.murano_metadata_url
    if not endpoint:
        keystone_settings = CONF.keystone

        client = ksclient.Client(auth_url=keystone_settings.auth_url,
                                 token=token_id)

        client.authenticate(
            auth_url=keystone_settings.auth_url,
            tenant_id=tenant_id,
            token=token_id)

        try:
            endpoint = client.service_catalog.url_for(
                service_type='murano-metadata')
        except EndpointNotFound:
            endpoint = 'http://localhost:8084/v1'
            log.warning(
                'Murano Metadata API location could not be found in the '
                'Keystone Service Catalog, using default: {0}'.format(
                    endpoint))
    return endpoint


def metadataclient(token_id, tenant_id):
    endpoint = get_endpoint(token_id, tenant_id)
    return Client(endpoint=endpoint, token=token_id)


def get_metadata(task_id, token_id, tenant_id):
    hash = _check_existing_hash()
    try:
        log.debug('Retrieving metadata from Murano Metadata Repository')
        resp, body_iter = metadataclient(token_id, tenant_id).\
            metadata_client.get_conductor_data(hash)
    except CommunicationError as e:
        if hash:
            log.warning('Metadata update failed: '
                        'Unable to connect Metadata Repository due to {0}. '
                        'Using existing version of metadata'.format(e))
        else:
            log.exception(e)
            exc_type, exc_value, exc_traceback = sys.exc_info()
            raise MetadataException('Unable to get data '
                                    'from Metadata Repository due to {0}: '
                                    '{1}'.format(exc_type.__name__, exc_value))

    else:
        if resp.status == 304:
            log.debug('Metadata unmodified. Using existing archive.')

        elif resp.status == 200:
            with tempfile.NamedTemporaryFile(delete=False) as archive:
                for chunk in body_iter:
                    archive.write(chunk)
            hash = _get_hash(archive.name)
            shutil.move(archive.name, hash + '.tar.gz')
        else:
            msg = 'Metadata update failed: '    \
                  'Got {0} status in response.'.format(resp.status)
            if hash:
                log.warning(msg + ' Using existing version of metadata.')
            else:
                raise MetadataException(msg)
    return _unpack_data_archive(task_id, hash)


def release(folder):
    log.debug('Deleting metadata folder {0}'.format(folder))
    try:
        shutil.rmtree(folder)
    except Exception as e:
        log.exception('Unable to delete folder {0} with '
                      'task metadata due to {1}'.format(folder, e))


def prepare(data_dir):
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
        log.info("Creating directory '{0}' to store "
                 "conductor data".format(data_dir))
    init_scripts_dst = os.path.join(data_dir,
                                    os.path.basename(CONF.init_scripts_dir))
    if os.path.exists(init_scripts_dst):
        log.info("Found existing init scripts directory at"
                 " '{0}'. Deleting it.'".format(init_scripts_dst))
        shutil.rmtree(init_scripts_dst)
    log.info("Copying init scripts directory from '{0}' "
             "to '{1}'".format(CONF.init_scripts_dir, init_scripts_dst))
    shutil.copytree(CONF.init_scripts_dir, init_scripts_dst)

    agent_config_dst = os.path.join(data_dir,
                                    os.path.basename(CONF.agent_config_dir))
    if os.path.exists(agent_config_dst):
        log.info("Found existing agent config directory at"
                 " '{0}'. Deleting it.'".format(agent_config_dst))
    log.info("Copying agent config directory from '{0}' "
             "to '{1}'".format(CONF.agent_config_dir, agent_config_dst))
    shutil.copytree(CONF.agent_config_dir, agent_config_dst)
    os.chdir(data_dir)


def _get_hash(archive_path):
    """Calculate SHA1-hash of archive file.

    SHA-1 take a bit more time than MD5 (see http://tinyurl.com/kpj5jy7),
    but is more secure.
    """
    if os.path.exists(archive_path):
        sha1 = hashlib.sha1()
        with open(archive_path) as f:
            buf = f.read(CHUNK_SIZE)
            while buf:
                sha1.update(buf)
                buf = f.read(CHUNK_SIZE)
        hsum = sha1.hexdigest()
        log.debug("Archive '{0}' has hash-sum {1}".format(archive_path, hsum))
        return hsum
    else:
        log.info("Archive '{0}' doesn't exist, no hash to calculate".format(
            archive_path))
        return None


def _check_existing_hash():
    hash_archives = glob('*.tar.gz')
    if not hash_archives:
        hash = None
    else:
        if len(hash_archives) > 1:
            log.warning('There are to metadata archive. Deleting them both')
            for item in hash_archives:
                os.remove(item)
                hash = None
        else:
            file_name, extension = hash_archives[0].split('.', 1)
            hash = file_name
    return hash
