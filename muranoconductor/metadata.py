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
import tarfile
import shutil
import tempfile
import hashlib
from muranoconductor import config
from metadataclient.v1.client import Client
import os
from openstack.common import log as logging

CHUNK_SIZE = 1 << 20  # 1MB
ARCHIVE_PKG_NAME = 'archive.tar.gz'
INIT_FILES_DIR_NAME = 'init-scripts'
AGENT_CONFIG_DIR_NAME = 'agent-config'
INIT_FILES_DIR = 'etc/' + INIT_FILES_DIR_NAME
AGENT_CONFIG_DIR = 'etc/' + AGENT_CONFIG_DIR_NAME
log = logging.getLogger(__name__)


def get_endpoint():
    # prefer location specified in settings for dev purposes
    endpoint = config.CONF.murano_metadata_url

    if not endpoint:
        #TODO: add keystone catalog lookup
        pass
    return endpoint


def metadataclient(token_id):
    endpoint = get_endpoint()
    return Client(endpoint=endpoint, token=token_id)


def unpack_data_archive(hash):
    if not tarfile.is_tarfile(ARCHIVE_PKG_NAME):
        raise RuntimeError('{0} is not '
                           'valid tarfile!'.format(ARCHIVE_PKG_NAME))
    if hash is None:
        hash = _get_hash(ARCHIVE_PKG_NAME)
    dst_dir = hash
    if not os.path.exists(dst_dir):
        os.mkdir(dst_dir)
    with tarfile.open(ARCHIVE_PKG_NAME, 'r:gz') as tar:
        tar.extractall(path=dst_dir)
    return dst_dir


def get_metadata(token_id):
    #TODO: Add hash checking by 304 code in response
    #
    hash = _get_hash(ARCHIVE_PKG_NAME)
    try:
        log.debug("Retrieving metadata from Murano Metadata Repository")
        resp, body_iter = \
            metadataclient(token_id).metadata_client.get_conductor_data(hash)
    except Exception as e:
        if hash:
            log.warning('Unable to connect Metadata Repository due to {0}.'
                        'Using existing version of metadata'.format(e))
        else:
            raise Exception('Unable to connect Metadata Repository')
    else:
        if resp.status == 304:
            log.debug('Using existing version of metadata')
        elif resp.status == 200:
            with tempfile.NamedTemporaryFile(delete=False) as out:
                for chunk in body_iter:
                    out.write(chunk)
            shutil.move(out.name, ARCHIVE_PKG_NAME)
            hash = _get_hash(ARCHIVE_PKG_NAME)
        #ToDo: Handle other error codes
    return unpack_data_archive(hash)


def release(folder):
    # TODO: Add checkup - if hash was not modified
    log.debug('Deleting metadata folder {0}'.format(folder))
    shutil.rmtree(folder)


def prepare(data_dir):
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    init_scripts_dst = os.path.join(data_dir, os.path.basename(INIT_FILES_DIR))
    if not os.path.exists(init_scripts_dst):
        shutil.copytree(INIT_FILES_DIR, init_scripts_dst)
    agent_config_dst = os.path.join(data_dir,
                                    os.path.basename(AGENT_CONFIG_DIR))
    if not os.path.exists(agent_config_dst):
        shutil.copytree(AGENT_CONFIG_DIR, agent_config_dst)
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
