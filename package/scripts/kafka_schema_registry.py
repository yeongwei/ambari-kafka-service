

from resource_management import Script
from resource_management.libraries.functions.check_process_status import check_process_status
from resource_management.libraries.functions.format import format
from resource_management.core.resources.system import Execute, File, Directory
from kafka import schema_registry

class KafkaSchemaRegistry(Script):
    def install(self, env):
        self.install_packages(env)
        
    def start(self, env):
        import params
        import status_params
        env.set_params(params)
        self.configure(env)
        start_cmd="{0} {1} 2>&1 1>{2}/schema-registry.log &".format(params.schema_registry_start, params.schema_registry_conf, params.kafka_managed_log_dir)
        print start_cmd
        Execute(start_cmd)
        get_pid_cmd='ps -ef | grep ' + params.schema_registry_conf + ' | grep -v grep | awk \'{print $2}\' | xargs echo -n > ' + status_params.schema_registry_pid_file
        print get_pid_cmd
        Execute(get_pid_cmd)
        
    def stop(self, env):
        import params
        import status_params
        env.set_params(params)
        stop_cmd="{0}".format(params.schema_registry_stop)  
        print stop_cmd
        Execute(stop_cmd)
        File (status_params.schema_registry_pid_file, action = "delete")

    def configure(self, env):
        import params
        env.set_params(params)
        schema_registry(env)        
                
    def status(self, env):
        import status_params
        env.set_params(status_params)
        check_process_status(status_params.schema_registry_pid_file)
        
if __name__ == "__main__":
  KafkaSchemaRegistry().execute()
