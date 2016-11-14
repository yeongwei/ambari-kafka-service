#!/usr/bin/env python
"""
Licensed to the Apache Software Foundation (ASF) under one
or more contributor license agreements.  See the NOTICE file
distributed with this work for additional information
regarding copyright ownership.  The ASF licenses this file
to you under the Apache License, Version 2.0 (the
"License"); you may not use this file except in compliance
with the License.  You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

"""
from resource_management.libraries.functions import format
from resource_management.libraries.script.script import Script
from resource_management.libraries.functions.version import format_hdp_stack_version, compare_versions
from resource_management.libraries.functions.default import default
from utils import get_bare_principal
from resource_management.libraries.functions.get_hdp_version import get_hdp_version
from resource_management.libraries.functions.is_empty import is_empty
import status_params
from resource_management.core.logger import Logger
from resource_management.libraries.resources.hdfs_resource import HdfsResource
from resource_management.libraries.functions import iop_select
from resource_management.libraries.functions import conf_select
from resource_management.libraries.functions import get_kinit_path


# server configurations
config = Script.get_config()
tmp_dir = Script.get_tmp_dir()
stack_name = default("/hostLevelParams/stack_name", None)
retryAble = default("/commandParams/command_retry_enabled", False)

# Version being upgraded/downgraded to
version = default("/commandParams/version", None)
# Version that is CURRENT.
current_version = default("/hostLevelParams/current_version", None)

host_sys_prepped = default("/hostLevelParams/host_sys_prepped", False)

stack_version_unformatted = str(config['hostLevelParams']['stack_version'])
iop_stack_version = format_hdp_stack_version(stack_version_unformatted)
upgrade_direction = default("/commandParams/upgrade_direction", None)

# When downgrading the 'version' and 'current_version' are both pointing to the downgrade-target version
# downgrade_from_version provides the source-version the downgrade is happening from
downgrade_from_version = default("/commandParams/downgrade_from_version", None)

hostname = config['hostname']

# default kafka parameters
kafka_home = '/usr/iop/current/kafka-broker'
kafka_bin = kafka_home+'/bin/kafka'
connect_bin = '/opt/IBM/npi/npi-connect/bin/connect.sh'
conf_dir = "/usr/iop/current/kafka-broker/config"
limits_conf_dir = "/etc/security/limits.d"

# Used while upgrading the stack in a kerberized cluster and running kafka-acls.sh
zookeeper_connect = default("/configurations/kafka-broker/zookeeper.connect", None)

kafka_user_nofile_limit = default("/configurations/kafka-env/kafka_user_nofile_limit", None)
kafka_user_nproc_limit = default("/configurations/kafka-env/kafka_user_nproc_limit", None)

kafka_user = config['configurations']['kafka-env']['kafka_user']
kafka_log_dir = config['configurations']['kafka-env']['kafka_log_dir']
kafka_pid_dir = status_params.kafka_pid_dir
kafka_pid_file = kafka_pid_dir+"/kafka.pid"
connect_pid_file = kafka_pid_dir+"/connect.pid"
# This is hardcoded on the kafka bash process lifecycle on which we have no control over
kafka_managed_pid_dir = "/var/run/kafka"
kafka_managed_log_dir = "/var/log/kafka"
user_group = config['configurations']['cluster-env']['user_group']
java64_home = config['hostLevelParams']['java_home']
kafka_env_sh_template = config['configurations']['kafka-env']['content']
kafka_hosts = config['clusterHostInfo']['kafka_broker_hosts']
kafka_hosts.sort()
zk_session_timeout = config['configurations']['kafka-broker']['zookeeper.session.timeout.ms']

zookeeper_hosts = config['clusterHostInfo']['zookeeper_hosts']
zookeeper_hosts.sort()

if (('kafka-log4j' in config['configurations']) and ('content' in config['configurations']['kafka-log4j'])):
    log4j_props = config['configurations']['kafka-log4j']['content']
else:
    log4j_props = None
    
if (('connect-log4j' in config['configurations']) and ('content' in config['configurations']['connect-log4j'])):
    connect_log4j_props = config['configurations']['connect-log4j']['content']
else:
    connect_log4j_props = None    

metric_collector_host = ""
metric_collector_port = ""

ams_collector_hosts = default("/clusterHostInfo/metrics_collector_hosts", [])
has_metric_collector = not len(ams_collector_hosts) == 0

if has_metric_collector:
  if 'cluster-env' in config['configurations'] and \
      'metrics_collector_vip_host' in config['configurations']['cluster-env']:
    metric_collector_host = config['configurations']['cluster-env']['metrics_collector_vip_host']
  else:
    metric_collector_host = ams_collector_hosts[0]
  if 'cluster-env' in config['configurations'] and \
      'metrics_collector_vip_port' in config['configurations']['cluster-env']:
    metric_collector_port = config['configurations']['cluster-env']['metrics_collector_vip_port']
  else:
    metric_collector_web_address = default("/configurations/ams-site/timeline.metrics.service.webapp.address", "0.0.0.0:6188")
    if metric_collector_web_address.find(':') != -1:
      metric_collector_port = metric_collector_web_address.split(':')[1]
    else:
      metric_collector_port = '6188'
  pass

# Security-related params
security_enabled = config['configurations']['cluster-env']['security_enabled']
kafka_kerberos_enabled = ('security.inter.broker.protocol' in config['configurations']['kafka-broker'] and
                          config['configurations']['kafka-broker']['security.inter.broker.protocol'] == "SASL_PLAINTEXT")

if security_enabled and iop_stack_version != "" and 'kafka_principal_name' in config['configurations']['kafka-env'] and compare_versions(iop_stack_version, '4.1') >= 0:
    _hostname_lowercase = config['hostname'].lower()
    _kafka_principal_name = config['configurations']['kafka-env']['kafka_principal_name']
    kafka_jaas_principal = _kafka_principal_name.replace('_HOST',_hostname_lowercase)
    kafka_keytab_path = config['configurations']['kafka-env']['kafka_keytab']
    kafka_bare_jaas_principal = get_bare_principal(_kafka_principal_name)
    kafka_kerberos_params = "-Djava.security.auth.login.config="+ conf_dir +"/kafka_jaas.conf"
else:
    kafka_kerberos_params = ''

namenode_hosts = default("/clusterHostInfo/namenode_host", [])
has_namenode = not len(namenode_hosts) == 0

hdfs_user = config['configurations']['hadoop-env']['hdfs_user'] if has_namenode else None
hdfs_user_keytab = config['configurations']['hadoop-env']['hdfs_user_keytab'] if has_namenode else None
hdfs_principal_name = config['configurations']['hadoop-env']['hdfs_principal_name'] if has_namenode else None
hdfs_site = config['configurations']['hdfs-site'] if has_namenode else None
default_fs = config['configurations']['core-site']['fs.defaultFS'] if has_namenode else None
hadoop_bin_dir = iop_select.get_hadoop_dir("bin") if has_namenode else None
hadoop_conf_dir = conf_select.get_hadoop_conf_dir() if has_namenode else None
kinit_path_local = get_kinit_path(default('/configurations/kerberos-env/executable_search_paths', None))

import functools
#create partial functions with common arguments for every HdfsResource call
#to create/delete hdfs directory/file/copyfromlocal we need to call params.HdfsResource in code
HdfsResource = functools.partial(
  HdfsResource,
  user=hdfs_user,
  security_enabled = security_enabled,
  keytab = hdfs_user_keytab,
  kinit_path_local = kinit_path_local,
  hadoop_bin_dir = hadoop_bin_dir,
  hadoop_conf_dir = hadoop_conf_dir,
  principal_name = hdfs_principal_name,
  hdfs_site = hdfs_site,
  default_fs = default_fs
)

# Kafka Schema Registry
schema_registry_start	= '/opt/IBM/npi/npi-schema-registry/bin/schema-registry-start'
schema_registry_stop 	= '/opt/IBM/npi/npi-schema-registry/bin/schema-registry-stop'
schema_registry_conf 	= '/opt/IBM/npi/npi-schema-registry/etc/schema-registry/schema-registry.properties'
schema_registry_log 	= kafka_managed_log_dir + '/schema-registry.log'
schema_registry_http	= config['configurations']['schema-registry-conf']['http.port']
schema_registry_topic	= config['configurations']['schema-registry-conf']['schema.registry.topic']
schema_registry_zk_url	= config['configurations']['kafka-broker']['zookeeper.connect']


