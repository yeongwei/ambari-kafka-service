

from resource_management import Script
from resource_management.libraries.functions.check_process_status import check_process_status
from resource_management.libraries.functions.format import format
from resource_management.core.resources.system import Execute, File, Directory
from kafka import connect

class KafkaConnect(Script):
    def install(self, env):
        self.install_packages(env)
        
    def start(self, env):
        import params
        env.set_params(params)
        self.configure(env)
        daemon_cmd = format('{params.connect_bin} start {params.connect_pid_file}')
        no_op_test = format('ls {params.connect_pid_file} >/dev/null 2>&1 && ps -p `cat {params.connect_pid_file}` >/dev/null 2>&1')
        Execute(daemon_cmd,
                user=params.kafka_user,
                not_if=no_op_test
        )
        
    def stop(self, env):
        import params
        env.set_params(params)
        daemon_cmd = format('{params.connect_bin} stop {params.connect_pid_file}')
        Execute(daemon_cmd,
                user=params.kafka_user,
        )
        File (params.connect_pid_file, 
              action = "delete"
        )
    def configure(self, env):
        import params
        env.set_params(params)
        connect(params.config['configurations']['kafka-broker'])        
                
    def status(self, env):
        import status_params
        env.set_params(status_params)
        check_process_status(status_params.connect_pid_file)
        
if __name__ == "__main__":
  KafkaConnect().execute()