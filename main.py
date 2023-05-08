import git, os, shutil, sys, base64, asyncio
from base.artifactory import *
from base.upload_to_s3 import *
from urllib.parse import urlparse
from base.print_log_message import *
from base.build_docker_image import *
from base.ecr_docker_registry import *
from base.archive_current_zip import *
from base.health_check_website import *
from base.get_secret_value_from_sm import *
from base.deploy_to_aws_environment import *
from base.default_env_variables_check import *
from base.replace_placeholders_in_file import *
from base.prepare_secrets_download_file import *
from base.environment_variables_file_preparation import *
from base.docker_composer_deployment_preparation import *

class TalechService:
    def __init__(self, talech_service, base_dir, aws_region, user, password, env, level, force_rebuild, build_only, aws_deployment, url, response_code, build_args, proxy, fail_on_missing_variables, template_dir, template_name, env_stage, use_local_variables_file, rewrite_variables_list):
        ### Seting up Class variables
        self.data = None
        self.talech_service=talech_service
        self.user=user
        self.password=password
        self.base_dir=base_dir
        self.source_code_path=f'{self.base_dir}/source_code'
        self.buid_dir=f'{self.base_dir}/build/build'
        self.output=f'{self.base_dir}/output'
        self.aws_region=aws_region
        self.ecr_url=self.ecr_registry()
        self.default_ecr_registry='082280121301.dkr.ecr.us-east-1.amazonaws.com'
        self.templates_base_dir=f'{self.base_dir}/templates'
        self.dict_of_secrets={}
        self.env=env
        self.level=level
        self.proxy=proxy
        self.force_rebuild=force_rebuild
        self.build_only=build_only
        self.aws_deployment=aws_deployment
        self.metrix_log4j_version="2.18.0"
        self.deployment_s3_bucket=f'talech-deployments-{self.aws_region}'
        self.url=url
        self.fail_on_missing_variables=fail_on_missing_variables
        self.env_stage=env_stage
        self.use_local_variables_file=use_local_variables_file
        self.rewrite_variables_list=rewrite_variables_list
        if self.force_rebuild:
            self.no_cache='--no-cache'
        else:
            self.no_cache=''

        ### Seting up talech service specific variables
        match self.talech_service:
            ######################################################################################################################################################
            case 'admin':
                self.product_name='admin'
                self.source_code=f'{self.source_code_path}/talech_admin'
                self.path_to_dockerfile=f'{self.source_code}'
                self.dockerfile_name='Dockerfile'
                self.docker_image_name=self.product_name
                self.docker_buildargs={}
                self.code_build_command=""
                self.env_vars_chech_enabled=True
                self.deployment_bucket_dir=f'admin_tool'
                self.expected_health_check_response_code=response_code
                self.branch_name_variable_jenkins='ADMIN_BRANCH_NAME'

                ### Add files where credentials should be updated
                self.list_of_files_to_update_creds=[
                    f'{self.source_code}/Dockerfile', 
                    f'{self.source_code}/composer.lock',
                    f'{self.source_code}/build-talech_admin.sh',
                    ]
                
                if template_dir == '':
                    self.template_location=f'{self.templates_base_dir}/admin'
                else:
                    self.template_location=f'{self.templates_base_dir}/{template_dir}'
                if template_name == '':
                    self.template_name="admin-dc-localvars.yaml.j2"
                else:
                    self.template_name=template_name

                if self.use_local_variables_file:
                    self.default_env_variables='deployments/secrets'
                    self.local_variables_dir=f'{self.source_code}/deployments'
                    if self.level == 'dev':
                        self.local_variables_file='variables_dev'
                        if self.aws_region == 'us-east-1':
                            self.environment_variables_from_secret='dev-us-admin-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.environment_variables_from_secret='dev-eu-admin-secrets'
                    elif self.level == 'stage':
                        self.local_variables_file='variables_stage'
                        if self.aws_region == 'us-east-1':
                            self.environment_variables_from_secret='stage-us-admin-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.environment_variables_from_secret='stage-eu-admin-secrets'
                    elif self.level == 'prod':
                        if self.aws_region == 'us-east-1':
                            self.local_variables_file='variables_prod_us'
                            self.environment_variables_from_secret='prod-us-admin-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.local_variables_file='variables_prod_eu'
                            self.environment_variables_from_secret='prod-eu-admin-secrets'
                else: 
                    self.default_env_variables='env.example'
                    if self.level == 'dev':
                        self.environment_variables_from_secret=f'local-{self.env}-admin-secrets'
                    else:
                        if 'admin-stage' == self.env:
                            self.environment_variables_from_secret=f'admin-stage-vars'
                        else:
                            self.environment_variables_from_secret=f'{self.env}-vars'

                if 'prod-us-1' in self.env:
                    self.aws_logs_group='admin-prod-us'
                elif 'prod-eu-1' in self.env:
                    self.aws_logs_group='admin-prod-eu'
                else:
                    self.aws_logs_group='admin-dev'

                if os.path.exists(self.source_code):
                    self.version=f'{self.get_git_branch(self.source_code).replace("/", "_")}_{self.get_git_hash(self.source_code)}'
                else:
                    print_log_message(log_level='ERROR', msg=f'Missing source coede {self.source_code}')
                    sys.exit(1)
                self.tag=f'{self.default_ecr_registry}/{self.docker_image_name}:{self.version}'
                self.docker_build_command=f'DOCKER_BUILDKIT=0 docker build -t {self.tag} -f {self.dockerfile_name} .  --progress plain --network=host {self.no_cache}'
            ######################################################################################################################################################
            case 'talech':
                self.product_name='talech'
                self.source_code=f'{self.source_code_path}/old_website'
                self.webfe_source_code=f'{self.source_code}/web_fe'
                self.path_to_dockerfile=f'{self.source_code}/'
                self.dockerfile_name='Dockerfile'
                self.docker_image_name=self.product_name
                self.docker_buildargs={}
                self.code_build_command=""
                self.env_vars_chech_enabled=True
                self.deployment_bucket_dir=f'talech_website'
                self.expected_health_check_response_code=response_code
                self.branch_name_variable_jenkins='TALECH_BRANCH_NAME'
                self.fe_branch_name_variable_jenkins='WEB_FE_BRANCH_NAME'

                self.list_of_files_to_update_creds=[
                    f'{self.source_code}/Dockerfile', 
                    f'{self.source_code}/composer.lock', 
                    f'{self.source_code}/package-lock.json', 
                    f'{self.source_code}/build-talech.sh',
                    f'{self.webfe_source_code}/yarn.lock',
                    ]

                if template_dir == '':
                    self.template_location=f'{self.templates_base_dir}/old_website'
                else:
                    self.template_location=f'{self.templates_base_dir}/{template_dir}'
                if template_name == '':
                    if 'ops' in self.env:
                        self.template_name="web-ops-dc-localvars.yaml.j2"
                    elif 'qa-1' in self.env:
                        self.template_name="web-qa-1-dc-localvars.yaml.j2"
                    elif 'stage-1' in self.env:
                        self.template_name="web-stage-1-dc-localvars.yaml.j2"
                    elif 'prod-us-1' in self.env:
                        self.template_name="web-prod-us-dc-localvars.yaml.j2"
                    elif 'prod-eu-1' in self.env:
                        self.template_name="web-prod-eu-dc-localvars.yaml.j2"
                    else:
                        self.template_name="web-dc-localvars.yaml.j2"
                else:
                    self.template_name=template_name

                if self.use_local_variables_file:
                    self.default_env_variables='deployments/secrets'
                    self.local_variables_dir=f'{self.source_code}/deployments'
                    if self.level == 'dev':
                        self.local_variables_file='variables_dev'
                        if self.aws_region == 'us-east-1':
                            self.environment_variables_from_secret='dev-us-web-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.environment_variables_from_secret='dev-eu-web-secrets'
                    elif self.level == 'stage':
                        self.local_variables_file='variables_stage'
                        if self.aws_region == 'us-east-1':
                            self.environment_variables_from_secret='stage-us-web-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.environment_variables_from_secret='stage-eu-web-secrets'
                    elif self.level == 'prod':
                        if self.aws_region == 'us-east-1':
                            self.local_variables_file='variables_prod_us'
                            self.environment_variables_from_secret='prod-us-web-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.local_variables_file='variables_prod_eu'
                            self.environment_variables_from_secret='prod-eu-web-secrets'
                else:
                    self.default_env_variables='env.example'
                    if self.level == 'dev':
                        self.environment_variables_from_secret=f'local-{self.env}-talech-secrets'
                    else:
                        if 'web-stage-1' == self.env:
                            self.environment_variables_from_secret=f'web-stage-vars'
                        elif 'web-ops' == self.env:
                            self.environment_variables_from_secret=f'web-ops-vars'
                        elif 'web-qa-1' == self.env:
                            self.environment_variables_from_secret=f'web-qa-vars'
                        elif 'web-qa-2' == self.env:
                            self.environment_variables_from_secret=f'web-qa2-vars'
                        else:
                            self.environment_variables_from_secret=f'{self.env}-vars'
                   
                if 'prod-us-1' in self.env:
                    self.aws_logs_group='web-prod-us'
                elif 'prod-eu-1' in self.env:
                    self.aws_logs_group='web-prod-eu'
                else:
                    self.aws_logs_group='website-talech'

                if os.path.exists(self.source_code):
                    self.version=f'{self.get_git_branch(self.source_code).replace("/", "_")}_{self.get_git_hash(self.source_code)}_{self.get_git_branch(self.webfe_source_code).replace("/", "_")}_{self.get_git_hash(self.webfe_source_code)}'
                else:
                    print_log_message(log_level='ERROR', msg=f'Missing source coede {self.source_code}')
                    sys.exit(1)
                self.tag=f'{self.default_ecr_registry}/{self.docker_image_name}:{self.version}'
                self.docker_build_command=f'DOCKER_BUILDKIT=0 docker build -t {self.tag} -f {self.dockerfile_name} .  --progress plain --network=host {self.no_cache}'
            ######################################################################################################################################################
            case 'old-cron':
                self.product_name='old-cron'
                self.source_code=f'{self.source_code_path}/old_website'
                self.path_to_dockerfile=f'{self.source_code}'
                self.dockerfile_name='Dockerfile_airflow'
                self.docker_image_name=self.product_name
                self.docker_buildargs={}
                self.code_build_command=""
                self.env_vars_chech_enabled=True
                self.deployment_bucket_dir=f'old_web_php_cron'
                self.expected_health_check_response_code=response_code
                self.branch_name_variable_jenkins='TALECH_BRANCH_NAME'
                
                self.list_of_files_to_update_creds=[
                    f'{self.source_code}/composer.lock',
                    ]

                if template_dir == '':
                    self.template_location=f'{self.templates_base_dir}/old_cron'
                else:
                    self.template_location=f'{self.templates_base_dir}/{template_dir}'
                if template_name == '':
                    self.template_name="old-cron-dc-localvars.yaml.j2"
                else:
                    self.template_name=template_name

                if self.use_local_variables_file:
                    self.default_env_variables='deployments/cron_secrets'
                    self.local_variables_dir=f'{self.source_code}/deployments'
                    if self.level == 'dev':
                        with open(f'{self.local_variables_dir}/variables_dev', 'r') as f:
                            content_web_vars = f.read()
                        with open(f'{self.local_variables_dir}/variables_cron_dev', 'r') as f:
                            content_airflow_vars = f.read()
                        self.local_variables_file='variables_airflow_dev'
                        merged_content = content_web_vars + "\n" + content_airflow_vars 
                        with open(f'{self.local_variables_dir}/{self.local_variables_file}', 'w+') as f:
                            f.write(merged_content)
                        if self.aws_region == 'us-east-1':
                            self.environment_variables_from_secret='dev-us-old-cron-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.environment_variables_from_secret='dev-eu-old-cron-secrets'     
                    elif self.level == 'stage':
                        with open(f'{self.local_variables_dir}/variables_stage', 'r') as f:
                            content_web_vars = f.read()
                        with open(f'{self.local_variables_dir}/variables_cron_stage', 'r') as f:
                            content_airflow_vars = f.read()
                        self.local_variables_file='variables_airflow_stage'
                        merged_content = content_web_vars + "\n" + content_airflow_vars 
                        with open(f'{self.local_variables_dir}/{self.local_variables_file}', 'w+') as f:
                            f.write(merged_content)
                        if self.aws_region == 'us-east-1':
                            self.environment_variables_from_secret='stage-us-old-cron-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.environment_variables_from_secret='stage-eu-old-cron-secrets'
                    elif self.level == 'prod':
                        if self.aws_region == 'us-east-1':
                            with open(f'{self.local_variables_dir}/variables_prod_us', 'r') as f:
                                content_web_vars = f.read()
                            with open(f'{self.local_variables_dir}/variables_cron_prod_us', 'r') as f:
                                content_airflow_vars = f.read()
                            self.local_variables_file='variables_airflow_prod_us'
                            merged_content = content_web_vars + "\n" + content_airflow_vars 
                            with open(f'{self.local_variables_dir}/{self.local_variables_file}', 'w+') as f:
                                f.write(merged_content)
                            self.environment_variables_from_secret='prod-us-old-cron-secrets'
                        elif self.aws_region == 'eu-west-1':
                            with open(f'{self.local_variables_dir}/variables_prod_eu', 'r') as f:
                                content_web_vars = f.read()
                            with open(f'{self.local_variables_dir}/variables_cron_prod_eu', 'r') as f:
                                content_airflow_vars = f.read()
                            self.local_variables_file='variables_airflow_prod_eu'
                            merged_content = content_web_vars + "\n" + content_airflow_vars 
                            with open(f'{self.local_variables_dir}/{self.local_variables_file}', 'w+') as f:
                                f.write(merged_content)
                            self.environment_variables_from_secret='prod-eu-old-cron-secrets'
                else:
                    self.default_env_variables='env.airflow.example'
                    if self.level == 'dev':
                        self.environment_variables_from_secret=f'local-{self.env}-old-cron-secrets'
                    elif 'web-cron-prod-us-1' == self.env:
                        self.environment_variables_from_secret=f'web-prod-us-vars'
                    elif 'web-cron-prod-eu-1' == self.env:
                        self.environment_variables_from_secret=f'web-prod-eu-vars'
                    else:
                        self.environment_variables_from_secret=f'{self.env}-vars'

                if 'prod-us-1' in self.env:
                    self.aws_logs_group='web-cron-prod-us'
                elif 'prod-eu-1' in self.env:
                    self.aws_logs_group='web-cron-prod-eu'
                else:
                    self.aws_logs_group='web-cron'

                if os.path.exists(self.source_code):
                    self.version=f'{self.get_git_branch(self.source_code).replace("/", "_")}_{self.get_git_hash(self.source_code)}'
                else:
                    print_log_message(log_level='ERROR', msg=f'Missing source coede {self.source_code}')
                    sys.exit(1)
                self.tag=f'{self.default_ecr_registry}/{self.docker_image_name}:{self.version}'
                self.docker_build_command=f'DOCKER_BUILDKIT=0 docker build -t {self.tag} -f {self.dockerfile_name} .  --progress plain --network=host {self.no_cache}'
            ######################################################################################################################################################
            case 'web-cron':
                self.product_name='web-cron'
                self.source_code=f'{self.source_code_path}/web_be'
                self.path_to_dockerfile=f'{self.source_code}'
                self.dockerfile_name='Dockerfile_airflow'
                self.docker_image_name=self.product_name
                self.docker_buildargs={}
                self.code_build_command=""
                self.env_vars_chech_enabled=True
                self.deployment_bucket_dir=f'web_php_cron'
                self.expected_health_check_response_code=response_code
                self.branch_name_variable_jenkins='WEB_BE_BRANCH_NAME'
                
                self.list_of_files_to_update_creds=[
                    f'{self.source_code}/composer.lock',
                    ]

                if template_dir == '':
                    self.template_location=f'{self.templates_base_dir}/web_cron'
                else:
                    self.template_location=f'{self.templates_base_dir}/{template_dir}'
                if template_name == '':
                    self.template_name="web-cron-dc-localvars.yaml.j2"
                else:
                    self.template_name=template_name

                if self.use_local_variables_file:
                    self.default_env_variables='deployments/cron_secrets'
                    self.local_variables_dir=f'{self.source_code}/deployments'
                    if self.level == 'dev':
                        with open(f'{self.local_variables_dir}/variables_dev', 'r') as f:
                            content_web_vars = f.read()
                        with open(f'{self.local_variables_dir}/variables_cron_dev', 'r') as f:
                            content_airflow_vars = f.read()
                        self.local_variables_file='variables_airflow_dev'
                        merged_content = content_web_vars + "\n" + content_airflow_vars 
                        with open(f'{self.local_variables_dir}/{self.local_variables_file}', 'w+') as f:
                            f.write(merged_content)
                        if self.aws_region == 'us-east-1':
                            self.environment_variables_from_secret='dev-us-web-cron-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.environment_variables_from_secret='dev-eu-web-cron-secrets'     
                    elif self.level == 'stage':
                        with open(f'{self.local_variables_dir}/variables_stage', 'r') as f:
                            content_web_vars = f.read()
                        with open(f'{self.local_variables_dir}/variables_cron_stage', 'r') as f:
                            content_airflow_vars = f.read()
                        self.local_variables_file='variables_airflow_stage'
                        merged_content = content_web_vars + "\n" + content_airflow_vars 
                        with open(f'{self.local_variables_dir}/{self.local_variables_file}', 'w+') as f:
                            f.write(merged_content)
                        if self.aws_region == 'us-east-1':
                            self.environment_variables_from_secret='stage-us-web-cron-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.environment_variables_from_secret='stage-eu-web-cron-secrets'
                    elif self.level == 'prod':
                        if self.aws_region == 'us-east-1':
                            with open(f'{self.local_variables_dir}/variables_prod_us', 'r') as f:
                                content_web_vars = f.read()
                            with open(f'{self.local_variables_dir}/variables_cron_prod_us', 'r') as f:
                                content_airflow_vars = f.read()
                            self.local_variables_file='variables_airflow_prod_us'
                            merged_content = content_web_vars + "\n" + content_airflow_vars 
                            with open(f'{self.local_variables_dir}/{self.local_variables_file}', 'w+') as f:
                                f.write(merged_content)
                            self.environment_variables_from_secret='prod-us-web-cron-secrets'
                        elif self.aws_region == 'eu-west-1':
                            with open(f'{self.local_variables_dir}/variables_prod_eu', 'r') as f:
                                content_web_vars = f.read()
                            with open(f'{self.local_variables_dir}/variables_cron_prod_eu', 'r') as f:
                                content_airflow_vars = f.read()
                            self.local_variables_file='variables_airflow_prod_eu'
                            merged_content = content_web_vars + "\n" + content_airflow_vars 
                            with open(f'{self.local_variables_dir}/{self.local_variables_file}', 'w+') as f:
                                f.write(merged_content)
                            self.environment_variables_from_secret='prod-eu-web-cron-secrets'
                else:
                    self.default_env_variables='env.airflow.example'
                    if self.level == 'dev':
                        self.environment_variables_from_secret=f'local-{self.env}-web-cron-secrets'
                    else:
                        self.environment_variables_from_secret=f'{self.env}-vars'

                if 'prod-us-1' in self.env:
                    self.aws_logs_group='web-nextgen-cron-prod-us'
                elif 'prod-eu-1' in self.env:
                    self.aws_logs_group='web-nextgen-cron-prod-eu'
                else:
                    self.aws_logs_group='web-nextgen-cron'

                if os.path.exists(self.source_code):
                    self.version=f'{self.get_git_branch(self.source_code).replace("/", "_")}_{self.get_git_hash(self.source_code)}'
                else:
                    print_log_message(log_level='ERROR', msg=f'Missing source coede {self.source_code}')
                    sys.exit(1)
                self.tag=f'{self.default_ecr_registry}/{self.docker_image_name}:{self.version}'
                self.docker_build_command=f'DOCKER_BUILDKIT=0 docker build -t {self.tag} -f {self.dockerfile_name} .  --progress plain --network=host {self.no_cache}'
            ######################################################################################################################################################
            case 'web-be':
                self.product_name='web-be'
                self.source_code=f'{self.source_code_path}/web_be'
                self.path_to_dockerfile=f'{self.source_code}'
                self.dockerfile_name='Dockerfile_wapi'
                self.docker_image_name=self.product_name
                self.docker_buildargs={}
                self.code_build_command=""
                self.env_vars_chech_enabled=True
                self.deployment_bucket_dir=f'web_be'
                self.expected_health_check_response_code=response_code
                self.branch_name_variable_jenkins='WEB_BE_BRANCH_NAME'
                
                self.list_of_files_to_update_creds=[
                    f'{self.source_code}/composer.lock',
                    ]

                if template_dir == '':
                    self.template_location=f'{self.templates_base_dir}/web_be'
                else:
                    self.template_location=f'{self.templates_base_dir}/{template_dir}'
                if template_name == '':
                    self.template_name="web-be-dc-localvars.yaml.j2"
                else:
                    self.template_name=template_name

                if self.use_local_variables_file:
                    self.default_env_variables='deployments/secrets'
                    self.local_variables_dir=f'{self.source_code}/deployments'
                    if self.level == 'dev':
                        self.local_variables_file='variables_dev'
                        if self.aws_region == 'us-east-1':
                            self.environment_variables_from_secret='dev-us-web-be-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.environment_variables_from_secret='dev-eu-web-be-secrets'
                    elif self.level == 'stage':
                        self.local_variables_file='variables_stage'
                        if self.aws_region == 'us-east-1':
                            self.environment_variables_from_secret='stage-us-web-be-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.environment_variables_from_secret='stage-eu-web-be-secrets'
                    elif self.level == 'prod':
                        if self.aws_region == 'us-east-1':
                            self.local_variables_file='variables_prod_us'
                            self.environment_variables_from_secret='prod-us-web-be-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.local_variables_file='variables_prod_eu'
                            self.environment_variables_from_secret='prod-eu-web-be-secrets'
                else: 
                    self.default_env_variables='env.example'
                    if self.level == 'dev':
                        self.environment_variables_from_secret=f'local-{self.env}-wapi-secrets'
                    else:
                        self.environment_variables_from_secret=f'{self.env}-vars'

                if 'wapi-prod-us-1' in self.env:
                    self.aws_logs_group='wapi-prod-us'
                elif 'wapi-prod-eu-1' in self.env:
                    self.aws_logs_group='wapi-prod-eu'
                else:
                    self.aws_logs_group='wapi'

                if os.path.exists(self.source_code):
                    self.version=f'{self.get_git_branch(self.source_code).replace("/", "_")}_{self.get_git_hash(self.source_code)}'
                else:
                    print_log_message(log_level='ERROR', msg=f'Missing source coede {self.source_code}')
                    sys.exit(1)
                self.tag=f'{self.default_ecr_registry}/{self.docker_image_name}:{self.version}'
                self.docker_build_command=f'DOCKER_BUILDKIT=0 docker build -t {self.tag} -f {self.dockerfile_name} .  --progress plain --network=host {self.no_cache}'
            ######################################################################################################################################################
            case 'microsite':
                self.product_name='microsite'
                self.source_code=f'{self.source_code_path}/microsite_frontend'
                self.path_to_dockerfile=f'{self.source_code}'
                self.dockerfile_name='Dockerfile_microsite'
                self.docker_image_name=self.product_name
                self.docker_buildargs={}
                self.code_build_command=""
                self.env_vars_chech_enabled=True
                self.deployment_bucket_dir=f'microsite'
                self.expected_health_check_response_code=response_code
                self.branch_name_variable_jenkins='MICROSITE_BRANCH_NAME'
                
                self.list_of_files_to_update_creds=[
                    f'{self.source_code}/yarn.lock',
                    ]

                if template_dir == '':
                    self.template_location=f'{self.templates_base_dir}/microsite'
                else:
                    self.template_location=f'{self.templates_base_dir}/{template_dir}'
                if template_name == '':
                    self.template_name="microsite-dc-localvars.yaml.j2"
                else:
                    self.template_name=template_name

                if self.use_local_variables_file:
                    self.default_env_variables='deployments/secrets'
                    self.local_variables_dir=f'{self.source_code}/deployments'
                    if self.level == 'dev':
                        self.local_variables_file='variables_dev'
                        if self.aws_region == 'us-east-1':
                            self.environment_variables_from_secret=''
                        elif self.aws_region == 'eu-west-1':
                            self.environment_variables_from_secret=''
                    elif self.level == 'stage':
                        self.local_variables_file='variables_stage'
                        if self.aws_region == 'us-east-1':
                            self.environment_variables_from_secret=''
                        elif self.aws_region == 'eu-west-1':
                            self.environment_variables_from_secret=''
                    elif self.level == 'prod':
                        if self.aws_region == 'us-east-1':
                            self.local_variables_file='variables_prod_us'
                            self.environment_variables_from_secret=''
                        elif self.aws_region == 'eu-west-1':
                            self.local_variables_file='variables_prod_eu'
                            self.environment_variables_from_secret=''
                else: 
                    self.default_env_variables='env.example'
                    if self.level == 'dev':
                        self.environment_variables_from_secret=f'local-{self.env}-microsite-secrets'
                    else:
                        self.environment_variables_from_secret=f'{self.env}-secrets'

                if 'microsite-prod-us-1' in self.env:
                    self.aws_logs_group='microsite-prod-us'
                elif 'microsite-prod-eu-1' in self.env:
                    self.aws_logs_group='microsite-prod-eu'
                else:
                    self.aws_logs_group='microsite-dev'

                if os.path.exists(self.source_code):
                    self.version=f'{self.get_git_branch(self.source_code).replace("/", "_")}_{self.get_git_hash(self.source_code)}'
                else:
                    print_log_message(log_level='ERROR', msg=f'Missing source coede {self.source_code}')
                    sys.exit(1)
                self.tag=f'{self.default_ecr_registry}/{self.docker_image_name}:{self.version}'
                self.docker_build_command=f'DOCKER_BUILDKIT=0 docker build -t {self.tag} -f {self.dockerfile_name} .  --progress plain --network=host {self.no_cache}'
            ######################################################################################################################################################
            case 'web-app':
                self.product_name='web-app'
                self.source_code=f'{self.source_code_path}/web_app'
                self.path_to_dockerfile=f'{self.source_code}'
                self.dockerfile_name='Dockerfile'
                self.docker_image_name=self.product_name
                self.docker_buildargs={}
                self.code_build_command=""
                self.env_vars_chech_enabled=True
                self.deployment_bucket_dir=f'web_app'
                self.expected_health_check_response_code=response_code
                self.branch_name_variable_jenkins='WEB_APP_BRANCH_NAME'
                
                self.list_of_files_to_update_creds=[
                    f'{self.source_code}/yarn.lock',
                    ]

                if template_dir == '':
                    self.template_location=f'{self.templates_base_dir}/web_app'
                else:
                    self.template_location=f'{self.templates_base_dir}/{template_dir}'
                if template_name == '':
                    self.template_name="web-app-dc-localvars.yaml.j2"
                else:
                    self.template_name=template_name

                if self.use_local_variables_file:
                    self.default_env_variables='deployments/secrets'
                    self.local_variables_dir=f'{self.source_code}/deployments'
                    if self.level == 'dev':
                        self.local_variables_file='variables_dev'
                        if self.aws_region == 'us-east-1':
                            self.environment_variables_from_secret=''
                        elif self.aws_region == 'eu-west-1':
                            self.environment_variables_from_secret=''
                    elif self.level == 'stage':
                        self.local_variables_file='variables_stage'
                        if self.aws_region == 'us-east-1':
                            self.environment_variables_from_secret=''
                        elif self.aws_region == 'eu-west-1':
                            self.environment_variables_from_secret=''
                    elif self.level == 'prod':
                        if self.aws_region == 'us-east-1':
                            self.local_variables_file='variables_prod_us'
                            self.environment_variables_from_secret=''
                        elif self.aws_region == 'eu-west-1':
                            self.local_variables_file='variables_prod_eu'
                            self.environment_variables_from_secret=''
                else: 
                    self.default_env_variables='env.example'
                    if self.level == 'dev':
                        self.environment_variables_from_secret=f'local-{self.env}-web-app-secrets'
                    else:
                        self.environment_variables_from_secret=f'{self.env}-vars'

                if 'web-app-prod-us-1' in self.env:
                    self.aws_logs_group='web-app-prod-us'
                elif 'web-app-prod-eu-1' in self.env:
                    self.aws_logs_group='web-app-prod-eu'
                else:
                    self.aws_logs_group='web-app-dev'

                if os.path.exists(self.source_code):
                    self.version=f'{self.get_git_branch(self.source_code).replace("/", "_")}_{self.get_git_hash(self.source_code)}'
                else:
                    print_log_message(log_level='ERROR', msg=f'Missing source coede {self.source_code}')
                    sys.exit(1)
                self.tag=f'{self.default_ecr_registry}/{self.docker_image_name}:{self.version}'
                self.docker_build_command=f'DOCKER_BUILDKIT=0 docker build -t {self.tag} -f {self.dockerfile_name} .  --progress plain --network=host {self.no_cache}'
            ######################################################################################################################################################
            case 'posservice':
                self.product_name='posservice'
                self.source_code=f'{self.source_code_path}/java_backend'
                self.path_to_dockerfile=f'{self.source_code}'
                self.dockerfile_name='Dockerfile_pos'
                self.docker_image_name=self.product_name
                self.docker_buildargs={}
                self.code_build_command="build_pos.sh posservice -T"
                self.env_vars_chech_enabled=True
                self.deployment_bucket_dir=f'talech_pos'
                self.expected_health_check_response_code=response_code
                self.branch_name_variable_jenkins='POSSERVICE_BRANCH_NAME'
                
                self.list_of_files_to_update_creds=[
                    f'{self.source_code}/docker_build_files/settings.xml',
                    f'{self.source_code}/Dockerfile_pos',
                    f'{self.source_code}/docker_build_files/sources.list',
                    ]

                if template_dir == '':
                    self.template_location=f'{self.templates_base_dir}/posservice'
                else:
                    self.template_location=f'{self.templates_base_dir}/{template_dir}'
                if template_name == '':
                    self.template_name="tomcat-dc-localvars.yaml.j2"
                else:
                    self.template_name=template_name

                if self.use_local_variables_file:
                    self.default_env_variables='deployments/posservice_secrets'
                    self.local_variables_dir=f'{self.source_code}/deployments'
                    if self.level == 'dev':
                        self.local_variables_file='variables_posservice_dev'
                        if self.aws_region == 'us-east-1':
                            self.environment_variables_from_secret='dev-us-posservice-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.environment_variables_from_secret='dev-eu-posservice-secrets'
                    elif self.level == 'stage':
                        self.local_variables_file='variables_posservice_stage'
                        if self.aws_region == 'us-east-1':
                            self.environment_variables_from_secret='stage-us-posservice-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.environment_variables_from_secret='stage-eu-posservice-secrets'
                    elif self.level == 'prod':
                        if self.aws_region == 'us-east-1':
                            if 'prod-us-1' in self.env:
                                self.local_variables_file='variables_posservice_prod_us_1'
                            elif 'prod-us-2' in self.env:
                                self.local_variables_file='variables_posservice_prod_us_2'
                            elif 'prod-us-3' in self.env:
                                self.local_variables_file='variables_posservice_prod_us_3'
                            elif 'prod-us-4' in self.env:
                                self.local_variables_file='variables_posservice_prod_us_4'
                            elif 'prod-us-5' in self.env:
                                self.local_variables_file='variables_posservice_prod_us_5'
                            elif 'prod-us-6' in self.env:
                                self.local_variables_file='variables_posservice_prod_us_6'
                            self.environment_variables_from_secret='prod-us-posservice-secrets'
                        elif self.aws_region == 'eu-west-1':
                            if 'prod-eu-1' in self.env:
                                self.local_variables_file='variables_posservice_prod_eu_1'
                            elif 'prod-eu-2' in self.env:
                                self.local_variables_file='variables_posservice_prod_eu_2'
                            elif 'prod-eu-5' in self.env:
                                self.local_variables_file='variables_posservice_prod_eu_5'
                            self.environment_variables_from_secret='prod-eu-posservice-secrets'
                else: 
                    self.default_env_variables='env.poservice.example'
                    if self.level == 'dev':
                        self.environment_variables_from_secret=f'local-{self.env}-pos-secrets'
                    else:
                        self.environment_variables_from_secret=f'{self.env}-vars'

                if 'prod-us' in self.env:
                    self.aws_logs_group='java-prod-us'
                elif 'prod-eu' in self.env:
                    self.aws_logs_group='java-prod-eu'
                else:
                    self.aws_logs_group='java_instances_stage'

                if os.path.exists(self.source_code):
                    self.version=f'{self.get_git_branch(self.source_code).replace("/", "_")}_{self.get_git_hash(self.source_code)}'
                else:
                    print_log_message(log_level='ERROR', msg=f'Missing source coede {self.source_code}')
                    sys.exit(1)
                self.tag=f'{self.default_ecr_registry}/{self.docker_image_name}:{self.version}'
                self.docker_build_command=f'DOCKER_BUILDKIT=0 docker build -t {self.tag} -f {self.dockerfile_name} .  --progress plain --network=host {self.no_cache}'
            ######################################################################################################################################################
            case 'intsrv':
                self.product_name='intsrv'
                self.source_code=f'{self.source_code_path}/java_backend'
                self.path_to_dockerfile=f'{self.source_code}'
                self.dockerfile_name='Dockerfile_intsrv'
                self.docker_image_name=self.product_name
                self.docker_buildargs={}
                self.code_build_command="build_pos.sh intsrv -T"
                self.env_vars_chech_enabled=True
                self.deployment_bucket_dir=f'talech_intsrv'
                self.expected_health_check_response_code=response_code
                self.branch_name_variable_jenkins='POSSERVICE_BRANCH_NAME'
                
                self.list_of_files_to_update_creds=[
                    f'{self.source_code}/docker_build_files/settings.xml',
                    f'{self.source_code}/Dockerfile_intsrv',
                    f'{self.source_code}/docker_build_files/sources.list',
                    ]

                if template_dir == '':
                    self.template_location=f'{self.templates_base_dir}/intsrv'
                else:
                    self.template_location=f'{self.templates_base_dir}/{template_dir}'
                if template_name == '':
                    self.template_name="tomcat-dc-localvars.yaml.j2"
                else:
                    self.template_name=template_name

                if self.use_local_variables_file:
                    self.default_env_variables='deployments/intsrv_secrets'
                    self.local_variables_dir=f'{self.source_code}/deployments'
                    if self.level == 'dev':
                        self.local_variables_file='variables_intsrv_dev'
                        if self.aws_region == 'us-east-1':
                            self.environment_variables_from_secret='dev-us-intsrv-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.environment_variables_from_secret='dev-eu-intsrv-secrets'
                    elif self.level == 'stage':
                        self.local_variables_file='variables_intsrv_stage'
                        if self.aws_region == 'us-east-1':
                            self.environment_variables_from_secret='stage-us-intsrv-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.environment_variables_from_secret='stage-eu-intsrv-secrets'
                    elif self.level == 'prod':
                        if self.aws_region == 'us-east-1':
                            self.local_variables_file='variables_intsrv_prod_us'
                            self.environment_variables_from_secret='prod-us-intsrv-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.local_variables_file='variables_intsrv_prod_eu'
                            self.environment_variables_from_secret='prod-eu-intsrv-secrets'
                else: 
                    self.default_env_variables='env.intsrv.example'
                    if self.level == 'dev':
                        self.environment_variables_from_secret=f'local-{self.env}-intsrv-secrets'
                    else:
                        self.environment_variables_from_secret=f'{self.env}-vars'

                if 'prod-us' in self.env:
                    self.aws_logs_group='java-prod-us'
                elif 'prod-eu' in self.env:
                    self.aws_logs_group='java-prod-eu'
                else:
                    self.aws_logs_group='java_instances_stage'

                if os.path.exists(self.source_code):
                    self.version=f'{self.get_git_branch(self.source_code).replace("/", "_")}_{self.get_git_hash(self.source_code)}'
                else:
                    print_log_message(log_level='ERROR', msg=f'Missing source coede {self.source_code}')
                    sys.exit(1)
                self.tag=f'{self.default_ecr_registry}/{self.docker_image_name}:{self.version}'
                self.docker_build_command=f'DOCKER_BUILDKIT=0 docker build -t {self.tag} -f {self.dockerfile_name} .  --progress plain --network=host {self.no_cache}'
            ######################################################################################################################################################
            case 'scheduler':
                self.product_name='scheduler'
                self.source_code=f'{self.source_code_path}/java_backend'
                self.path_to_dockerfile=f'{self.source_code}'
                self.dockerfile_name='Dockerfile_scheduler'
                self.docker_image_name=self.product_name
                self.docker_buildargs={}
                self.code_build_command="build_pos.sh scheduler -T"
                self.env_vars_chech_enabled=True
                self.deployment_bucket_dir=f'talech_scheduler'
                self.expected_health_check_response_code=response_code
                self.branch_name_variable_jenkins='POSSERVICE_BRANCH_NAME'
                
                self.list_of_files_to_update_creds=[
                    f'{self.source_code}/docker_build_files/settings.xml',
                    f'{self.source_code}/Dockerfile_scheduler',
                    f'{self.source_code}/docker_build_files/sources.list',
                    ]

                if template_dir == '':
                    self.template_location=f'{self.templates_base_dir}/scheduler'
                else:
                    self.template_location=f'{self.templates_base_dir}/{template_dir}'
                if template_name == '':
                    self.template_name="tomcat-dc-localvars.yaml.j2"
                else:
                    self.template_name=template_name

                if self.use_local_variables_file:
                    self.default_env_variables='deployments/scheduler_secrets'
                    self.local_variables_dir=f'{self.source_code}/deployments'
                    if self.level == 'dev':
                        self.local_variables_file='variables_scheduler_dev'
                        if self.aws_region == 'us-east-1':
                            self.environment_variables_from_secret='dev-us-scheduler-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.environment_variables_from_secret='dev-eu-scheduler-secrets'
                    elif self.level == 'stage':
                        self.local_variables_file='variables_scheduler_stage'
                        if self.aws_region == 'us-east-1':
                            self.environment_variables_from_secret='stage-us-scheduler-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.environment_variables_from_secret='stage-eu-scheduler-secrets'
                    elif self.level == 'prod':
                        if self.aws_region == 'us-east-1':
                            self.local_variables_file='variables_scheduler_prod_us'
                            self.environment_variables_from_secret='prod-us-scheduler-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.local_variables_file='variables_scheduler_prod_eu'
                            self.environment_variables_from_secret='prod-eu-scheduler-secrets'
                else: 
                    self.default_env_variables='env.scheduler.example'
                    if self.level == 'dev':
                        self.environment_variables_from_secret=f'local-{self.env}-scheduler-secrets'
                    else:
                        self.environment_variables_from_secret=f'{self.env}-vars'

                if 'prod-us' in self.env:
                    self.aws_logs_group='java-prod-us'
                elif 'prod-eu' in self.env:
                    self.aws_logs_group='java-prod-eu'
                else:
                    self.aws_logs_group='java_instances_stage'

                if os.path.exists(self.source_code):
                    self.version=f'{self.get_git_branch(self.source_code).replace("/", "_")}_{self.get_git_hash(self.source_code)}'
                else:
                    print_log_message(log_level='ERROR', msg=f'Missing source coede {self.source_code}')
                    sys.exit(1)
                self.tag=f'{self.default_ecr_registry}/{self.docker_image_name}:{self.version}'
                self.docker_build_command=f'DOCKER_BUILDKIT=0 docker build -t {self.tag} -f {self.dockerfile_name} .  --progress plain --network=host {self.no_cache}' 
            ######################################################################################################################################################
            case 'extsrv':
                self.product_name='extsrv'
                self.source_code=f'{self.source_code_path}/thirdparty_services'
                self.extsrv_fe_source=f'{self.source_code}/frontend'
                self.path_to_dockerfile=f'{self.source_code}'
                self.dockerfile_name='Dockerfile_extsrv'
                self.docker_image_name=self.product_name
                self.docker_buildargs=build_args
                self.code_build_command=""
                self.env_vars_chech_enabled=True
                self.deployment_bucket_dir=f'ext_services'
                self.expected_health_check_response_code=response_code
                self.branch_name_variable_jenkins='EXTSRV_BRANCH_NAME'
                self.fe_branch_name_variable_jenkins='EXTSRV_BRANCH_FE_NAME'

                self.list_of_files_to_update_creds=[
                    f'{self.source_code}/docker/auth.json',
                    f'{self.source_code}/docker/sources.list',
                    f'{self.source_code}/docker/.npmrc_using_npm',
                    f'{self.source_code}/docker/.npmrc_using_yarn',
                    f'{self.source_code}/docker/artifactory.conf',
                    f'{self.source_code}/yarn.lock',
                    f'{self.source_code}/composer.lock',
                    f'{self.source_code}/frontend/yarn.lock',
                    ]

                if template_dir == '':
                    self.template_location=f'{self.templates_base_dir}/extsrv'
                else:
                    self.template_location=f'{self.templates_base_dir}/{template_dir}'
                if template_name == '':
                    self.template_name="extsrv-dc-localvars.yaml.j2"
                else:
                    self.template_name=template_name

                if self.use_local_variables_file:
                    self.default_env_variables='deployments/secrets'
                    self.local_variables_dir=f'{self.source_code}/deployments'
                    if self.level == 'dev':
                        self.local_variables_file='variables_dev'
                        if self.aws_region == 'us-east-1':
                            self.environment_variables_from_secret='dev-us-extsrv-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.environment_variables_from_secret='dev-eu-extsrv-secrets'
                    elif self.level == 'stage':
                        self.local_variables_file='variables_stage'
                        if self.aws_region == 'us-east-1':
                            self.environment_variables_from_secret='stage-us-extsrv-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.environment_variables_from_secret='stage-eu-extsrv-secrets'
                    elif self.level == 'prod':
                        if self.aws_region == 'us-east-1':
                            self.local_variables_file='variables_prod_us'
                            self.environment_variables_from_secret='prod-us-extsrv-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.local_variables_file='variables_prod_eu'
                            self.environment_variables_from_secret='prod-eu-extsrv-secrets'
                else:
                    self.default_env_variables='env.extsrv.example'
                    if self.level == 'dev':
                        self.environment_variables_from_secret=f'local-{self.env}-extsrv-secrets'
                    else:
                        self.environment_variables_from_secret=f'{self.env}-vars'

                if 'prod-us' in self.env:
                    self.aws_logs_group='extsrv-prod-us'
                elif 'prod-eu' in self.env:
                    self.aws_logs_group='extsrv-prod-eu'
                else:
                    self.aws_logs_group='extsrv-dev'

                if os.path.exists(self.source_code):
                    self.version=f'{self.get_git_branch(self.source_code).replace("/", "_")}_{self.get_git_hash(self.source_code)}_{self.get_git_branch(self.extsrv_fe_source).replace("/", "_")}_{self.get_git_hash(self.extsrv_fe_source)}'
                else:
                    print_log_message(log_level='ERROR', msg=f'Missing source coede {self.source_code}')
                    sys.exit(1)
                self.tag=f'{self.default_ecr_registry}/{self.docker_image_name}:{self.version}'
                self.docker_build_command=f'''DOCKER_BUILDKIT=1 docker build \
                                                --secret id=auth_json,src={self.source_code}/docker/auth.json \
                                                --secret id=artifactory_conf,src={self.source_code}/docker/artifactory.conf \
                                                --secret id=npmrc_using_npm,src={self.source_code}/docker/.npmrc_using_npm \
                                                --secret id=npmrc_using_yarn,src={self.source_code}/docker/.npmrc_using_yarn \
                                                --build-arg {self.docker_buildargs} \
                                                -t {self.tag} -f {self.dockerfile_name} .  --progress plain --network=host {self.no_cache}'''
            ######################################################################################################################################################
            case 'metrix-api':
                self.product_name='metrix-api'
                self.source_code=f'{self.source_code_path}/data_api'
                self.path_to_dockerfile=f'{self.source_code}/data-service'
                self.dockerfile_name='Dockerfile'
                self.docker_image_name=self.product_name
                self.docker_buildargs={}
                self.code_build_command=""
                self.env_vars_chech_enabled=True
                self.deployment_bucket_dir=f'metrix_api'
                self.expected_health_check_response_code=response_code
                self.branch_name_variable_jenkins='DATA_API_BRANCH_NAME'
                
                self.list_of_files_to_update_creds=[
                    f'{self.source_code}/artifactory-secret.example/settings.xml',
                    ]

                if template_dir == '':
                    self.template_location=f'{self.templates_base_dir}/api_metrix'
                else:
                    self.template_location=f'{self.templates_base_dir}/{template_dir}'
                if template_name == '':
                    self.template_name="api-metrix-dc-localvars.yaml.j2"
                else:
                    self.template_name=template_name

                if self.use_local_variables_file:
                    self.default_env_variables='deployments/secrets'
                    self.local_variables_dir=f'{self.source_code}/deployments'
                    if self.level == 'dev':
                        self.local_variables_file='variables_dev'
                        if self.aws_region == 'us-east-1':
                            self.environment_variables_from_secret='dev-us-metrix-api-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.environment_variables_from_secret='dev-eu-metrix-api-secrets'
                    elif self.level == 'stage':
                        self.local_variables_file='variables_stage'
                        if self.aws_region == 'us-east-1':
                            self.environment_variables_from_secret='stage-us-metrix-api-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.environment_variables_from_secret='stage-eu-metrix-api-secrets'
                    elif self.level == 'prod':
                        if self.aws_region == 'us-east-1':
                            self.local_variables_file='variables_prod_us'
                            self.environment_variables_from_secret='prod-us-metrix-api-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.local_variables_file='variables_prod_eu'
                            self.environment_variables_from_secret='prod-eu-metrix-api-secrets'
                else:
                    self.default_env_variables='env.example'
                    if self.level == 'dev':
                        self.environment_variables_from_secret=f'local-{self.env}-metrix-api-secrets'
                    else:
                        self.environment_variables_from_secret=f'{self.env}-vars'

                if 'prod-us' in self.env:
                    self.aws_logs_group='metrix-prod'
                elif 'prod-eu' in self.env:
                    self.aws_logs_group='metrix-prod'
                else:
                    self.aws_logs_group='metrix'

                if os.path.exists(self.source_code):
                    self.version=f'{self.get_git_branch(self.source_code).replace("/", "_")}_{self.get_git_hash(self.source_code)}'
                else:
                    print_log_message(log_level='ERROR', msg=f'Missing source coede {self.source_code}')
                    sys.exit(1)
                self.tag=f'{self.default_ecr_registry}/{self.docker_image_name}:{self.version}'
                self.docker_build_command=f'''DOCKER_BUILDKIT=1 docker build \
                                                --secret id=maven,src={self.source_code}/artifactory-secret.example/settings.xml \
                                                -t {self.tag} -f {self.dockerfile_name} .  --progress plain --network=host {self.no_cache}'''
            ######################################################################################################################################################
            case 'metrix-airflow':
                self.product_name='metrix-airflow'
                self.source_code=f'{self.source_code_path}/data_pipeline'
                self.path_to_dockerfile=f'{self.source_code}/airflow-docker/airflow'
                self.dockerfile_name='Dockerfile'
                self.docker_image_name=self.product_name
                self.docker_buildargs={}
                self.code_build_command=""
                self.env_vars_chech_enabled=True
                self.deployment_bucket_dir=f'metrix_airflow'
                self.expected_health_check_response_code=response_code
                self.branch_name_variable_jenkins='METRIX_BRANCH_NAME'
                
                self.list_of_files_to_update_creds=[
                    f'{self.source_code}/artifactory-secret.example/pip.conf',
                    f'{self.source_code}/artifactory-secret.example/sources.list',
                ]

                if template_dir == '':
                    self.template_location=f'{self.templates_base_dir}/airflow_metrix'
                else:
                    self.template_location=f'{self.templates_base_dir}/{template_dir}'
                if template_name == '':
                    self.template_name="metrix-airflow-dc-localvars.yaml.j2"
                else:
                    self.template_name=template_name

                if self.use_local_variables_file:
                    self.default_env_variables='deployments/airflow_secrets'
                    self.local_variables_dir=f'{self.source_code}/deployments'
                    if self.level == 'dev':
                        self.local_variables_file='variables_airflow_dev'
                        if self.aws_region == 'us-east-1':
                            self.environment_variables_from_secret='dev-us-metrix-airflow-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.environment_variables_from_secret='dev-eu-metrix-airflow-secrets'
                    elif self.level == 'stage':
                        self.local_variables_file='variables_airflow_stage'
                        if self.aws_region == 'us-east-1':
                            self.environment_variables_from_secret='stage-us-metrix-airflow-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.environment_variables_from_secret='stage-eu-metrix-airflow-secrets'
                    elif self.level == 'prod':
                        if self.aws_region == 'us-east-1':
                            self.local_variables_file='variables_airflow_prod_us'
                            self.environment_variables_from_secret='prod-us-metrix-airflow-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.local_variables_file='variables_airflow_prod_eu'
                            self.environment_variables_from_secret='prod-eu-metrix-airflow-secrets'
                else:
                    self.default_env_variables='env.airflow.example'
                    if self.level == 'dev':
                        self.environment_variables_from_secret=f'local-{self.env}-metrix-airflow-secrets'
                    else:
                        self.environment_variables_from_secret=f'{self.env}-vars'

                if 'prod-us' in self.env:
                    self.aws_logs_group='metrix-prod'
                elif 'prod-eu' in self.env:
                    self.aws_logs_group='metrix-prod'
                else:
                    self.aws_logs_group='metrix'

                if os.path.exists(self.source_code):
                    self.version=f'{self.get_git_branch(self.source_code).replace("/", "_")}_{self.get_git_hash(self.source_code)}'
                else:
                    print_log_message(log_level='ERROR', msg=f'Missing source coede {self.source_code}')
                    sys.exit(1)
                self.tag=f'{self.default_ecr_registry}/{self.docker_image_name}:{self.version}'
                self.docker_build_command=f'''DOCKER_BUILDKIT=1 docker build \
                                                --secret id=pip,src={self.source_code}/artifactory-secret.example/pip.conf \
                                                --secret id=apt,src={self.source_code}/artifactory-secret.example/sources.list \
                                                -t {self.tag} -f {self.dockerfile_name} .  --progress plain --network=host {self.no_cache}'''
            ######################################################################################################################################################
            case 'metrix-druid-master':
                self.product_name='metrix-druid-master'
                self.source_code=f'{self.source_code_path}/data_pipeline'
                self.path_to_dockerfile=f'{self.source_code}/druid-docker/druid'
                self.dockerfile_name='Dockerfile'
                self.docker_image_name="metrix-druid"
                self.docker_buildargs={}
                self.code_build_command=""
                self.env_vars_chech_enabled=True
                self.deployment_bucket_dir=f'metrix_druid_master'
                self.expected_health_check_response_code=response_code
                self.branch_name_variable_jenkins='METRIX_BRANCH_NAME'
                self.list_of_files_to_update_creds=[
                    f'{self.source_code}/druid-docker/druid/Dockerfile_druid',
                ]

                if template_dir == '':
                    self.template_location=f'{self.templates_base_dir}/druid_metrix'
                else:
                    self.template_location=f'{self.templates_base_dir}/{template_dir}'
                if template_name == '':
                    self.template_name="druid-master-dc-localvars.yaml.j2"
                else:
                    self.template_name=template_name

                if self.use_local_variables_file:
                    self.default_env_variables='deployments/druid_secrets'
                    self.local_variables_dir=f'{self.source_code}/deployments'
                    if self.level == 'dev':
                        self.local_variables_file='variables_druid_dev'
                        if self.aws_region == 'us-east-1':
                            self.environment_variables_from_secret='dev-us-druid-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.environment_variables_from_secret='dev-eu-druid-secrets'
                    elif self.level == 'stage':
                        if 'druid-master-stage-1' == self.env:
                            self.local_variables_file_1=f'variables_druid_coordinator_1_stage_1'
                            self.local_variables_file_2=f'variables_zookeeper_master'
                        elif 'druid-master-2-stage-1' == self.env:
                            self.local_variables_file_1=f'variables_druid_coordinator_2_stage_1'
                            self.local_variables_file_2=f'variables_zookeeper_worker'
                        elif 'druid-master-stage-2' == self.env:
                            self.local_variables_file_1=f'variables_druid_coordinator_1_stage_2'
                            self.local_variables_file_2=f'variables_zookeeper_master'
                        elif 'druid-master-2-stage-2' == self.env:
                            self.local_variables_file_1=f'variables_druid_coordinator_2_stage_2'
                            self.local_variables_file_2=f'variables_zookeeper_worker'
                        elif 'druid-master-stage-3' == self.env:
                            self.local_variables_file_1=f'variables_druid_coordinator_1_stage_3'
                            self.local_variables_file_2=f'variables_zookeeper_master'
                        elif 'druid-master-2-stage-3' == self.env:
                            self.local_variables_file_1=f'variables_druid_coordinator_2_stage_3'
                            self.local_variables_file_2=f'variables_zookeeper_worker'
                        elif 'druid-master-stage-4' == self.env:
                            self.local_variables_file_1=f'variables_druid_coordinator_1_stage_4'
                            self.local_variables_file_2=f'variables_zookeeper_master'
                        elif 'druid-master-2-stage-4' == self.env:
                            self.local_variables_file_1=f'variables_druid_coordinator_2_stage_4'
                            self.local_variables_file_2=f'variables_zookeeper_worker'
                        elif 'druid-master-ops-1' == self.env:
                            self.local_variables_file_1=f'variables_druid_coordinator_1_ops_1'
                            self.local_variables_file_2=f'variables_zookeeper_master'
                        elif 'druid-master-2-ops-1' == self.env:
                            self.local_variables_file_1=f'variables_druid_coordinator_2_ops_1'
                            self.local_variables_file_2=f'variables_zookeeper_worker'
                        elif 'druid-master-qa-1' == self.env:
                            self.local_variables_file_1=f'variables_druid_coordinator_1_qa_1'
                            self.local_variables_file_2=f'variables_zookeeper_master'
                        elif 'druid-master-2-qa-1' == self.env:
                            self.local_variables_file_1=f'variables_druid_coordinator_2_qa_1'
                            self.local_variables_file_2=f'variables_zookeeper_worker'
                        elif 'druid-master-qa-2' == self.env:
                            self.local_variables_file_1=f'variables_druid_coordinator_1_qa_2'
                            self.local_variables_file_2=f'variables_zookeeper_master'
                        elif 'druid-master-2-qa-2' == self.env:
                            self.local_variables_file_1=f'variables_druid_coordinator_2_qa_2'
                            self.local_variables_file_2=f'variables_zookeeper_worker'
                        elif 'druid-master-stage-eu-1' == self.env:
                            self.local_variables_file_1=f'variables_druid_coordinator_1_stage_eu_1'
                            self.local_variables_file_2=f'variables_zookeeper_master'
                        elif 'druid-master-2-stage-eu-1' == self.env:
                            self.local_variables_file_1=f'variables_druid_coordinator_2_stage_eu_1'
                            self.local_variables_file_2=f'variables_zookeeper_master'
                        if self.aws_region == 'us-east-1':
                            self.environment_variables_from_secret='stage-us-druid-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.environment_variables_from_secret='stage-eu-druid-secrets'
                    elif self.level == 'prod':
                        if self.aws_region == 'us-east-1':
                            self.environment_variables_from_secret='prod-us-druid-secrets'
                            if 'druid-master-prod-us-1' == self.env:
                                self.local_variables_file_1=f'variables_druid_coordinator_prod_us_1'
                                self.local_variables_file_2=f'variables_zookeeper_master'
                            elif 'druid-master-prod-us-2' == self.env:
                                self.local_variables_file_1=f'variables_druid_coordinator_prod_us_2'
                                self.local_variables_file_2=f'variables_zookeeper_worker'
                        elif self.aws_region == 'eu-west-1':
                            self.environment_variables_from_secret='prod-eu-druid-secrets'
                            if 'druid-master-prod-eu-1' == self.env:
                                self.local_variables_file_1=f'variables_druid_coordinator_prod_eu_1'
                                self.local_variables_file_2=f'variables_zookeeper_master'
                            elif 'druid-master-prod-eu-2' == self.env:
                                self.local_variables_file_1=f'variables_druid_coordinator_prod_eu_2'
                                self.local_variables_file_2=f'variables_zookeeper_worker'
                else:
                    self.default_env_variables='env.druid.example'
                    if self.level == 'dev':
                        self.environment_variables_from_secret=''
                    elif self.level == 'prod':
                        self.environment_variables_from_secret=f'{self.env}-coordinator-vars'
                    else:
                        if 'druid-master-stage-1' == self.env:
                            self.environment_variables_from_secret=f'druid-master-stage-1-coordinator-vars'
                        elif 'druid-master-2-stage-1' == self.env:
                            self.environment_variables_from_secret=f'druid-master-2-stage-1-coordinator-vars'
                        elif 'druid-master-stage-2' == self.env:
                            self.environment_variables_from_secret=f'druid-master-stage-2-coordinator-vars'
                        elif 'druid-master-2-stage-2' == self.env:
                            self.environment_variables_from_secret=f'druid-master-2-stage-2-coordinator-vars'
                        elif 'druid-master-stage-3' == self.env:
                            self.environment_variables_from_secret=f'druid-master-stage-3-coordinator-vars'
                        elif 'druid-master-2-stage-3' == self.env:
                            self.environment_variables_from_secret=f'druid-master-2-stage-3-coordinator-vars'
                        elif 'druid-master-stage-4' == self.env:
                            self.environment_variables_from_secret=f'druid-master-stage-4-coordinator-vars'
                        elif 'druid-master-2-stage-4' == self.env:
                            self.environment_variables_from_secret=f'druid-master-2-stage-4-coordinator-vars'
                        elif 'druid-master-ops-1' == self.env:
                            self.environment_variables_from_secret=f'druid-master-ops-1-coordinator-vars'
                        elif 'druid-master-2-ops-1' == self.env:
                            self.environment_variables_from_secret=f'druid-master-2-ops-1-coordinator-vars'
                        elif 'druid-master-qa-1' == self.env:
                            self.environment_variables_from_secret=f'druid-master-qa-1-coordinator-vars'
                        elif 'druid-master-2-qa-1' == self.env:
                            self.environment_variables_from_secret=f'druid-master-2-qa-1-coordinator-vars'
                        elif 'druid-master-qa-2' == self.env:
                            self.environment_variables_from_secret=f'druid-master-qa-2-coordinator-vars'
                        elif 'druid-master-2-qa-2' == self.env:
                            self.environment_variables_from_secret=f'druid-master-2-qa-2-coordinator-vars'
                        elif 'druid-master-prod-us-1' == self.env:
                            self.environment_variables_from_secret=f'druid-master-prod-us-1-coordinator-vars'
                        elif 'druid-master-2-prod-us-1' == self.env:
                            self.environment_variables_from_secret=f'druid-master-2-prod-us-1-coordinator-vars'
                        elif 'druid-master-prod-eu-1' == self.env:
                            self.environment_variables_from_secret=f'druid-master-prod-eu-1-coordinator-vars'
                        elif 'druid-master-2-prod-eu-1' == self.env:
                            self.environment_variables_from_secret=f'druid-master-2-prod-eu-1-coordinator-vars'
                        elif 'druid-master-stage-eu-1' == self.env:
                            self.environment_variables_from_secret=f'druid-master-stage-eu-1-coordinator-vars'
                        elif 'druid-master-2-stage-eu-1' == self.env:
                            self.environment_variables_from_secret=f'druid-master-2-stage-eu-1-coordinator-vars'

                if 'prod-us' in self.env:
                    self.aws_logs_group='metrix-prod'
                elif 'prod-eu' in self.env:
                    self.aws_logs_group='metrix-prod'
                else:
                    self.aws_logs_group='metrix'

                self.druid_user=return_secret_value_from_sm(
                                                                secret_name=self.environment_variables_from_secret, 
                                                                region=self.aws_region, 
                                                                secret_to_return='druid_escalator_internalClientUsernam')
                self.druid_password=return_secret_value_from_sm(
                                                                secret_name=self.environment_variables_from_secret, 
                                                                region=self.aws_region, 
                                                                secret_to_return='druid_escalator_internalClientPassword')

                self.url=self.add_credentials(self.druid_user, self.druid_password)

                if os.path.exists(self.source_code):
                    self.version=f'{self.get_git_branch(self.source_code).replace("/", "_")}_{self.get_git_hash(self.source_code)}'
                else:
                    print_log_message(log_level='ERROR', msg=f'Missing source coede {self.source_code}')
                    sys.exit(1)
                self.tag=f'{self.default_ecr_registry}/{self.docker_image_name}:{self.version}'
                self.docker_build_command=f'''docker build \
                                                --build-arg log4j_version={self.metrix_log4j_version} \
                                                --build-arg artifactory_user={self.user} \
                                                --build-arg artifactory_pass={self.password} \
                                                -t {self.tag} -f {self.dockerfile_name} .  --progress plain --network=host {self.no_cache}'''
            ######################################################################################################################################################
            case 'metrix-druid-query':
                self.product_name='metrix-druid-query'
                self.source_code=f'{self.source_code_path}/data_pipeline'
                self.path_to_dockerfile=f'{self.source_code}/druid-docker/druid'
                self.dockerfile_name='Dockerfile'
                self.docker_image_name="metrix-druid"
                self.docker_buildargs={}
                self.code_build_command=""
                self.env_vars_chech_enabled=True
                self.deployment_bucket_dir=f'metrix_druid_query'
                self.expected_health_check_response_code=response_code
                self.branch_name_variable_jenkins='METRIX_BRANCH_NAME'
                
                self.list_of_files_to_update_creds=[
                    f'{self.source_code}/druid-docker/druid/Dockerfile_druid',
                ]

                
                if template_dir == '':
                    self.template_location=f'{self.templates_base_dir}/druid_metrix'
                else:
                    self.template_location=f'{self.templates_base_dir}/{template_dir}'
                if template_name == '':
                    self.template_name="druid-query-dc-localvars.yaml.j2"
                else:
                    self.template_name=template_name

                if self.use_local_variables_file:
                    self.default_env_variables='deployments/druid_secrets'
                    self.local_variables_dir=f'{self.source_code}/deployments'
                    if self.level == 'dev':
                        self.local_variables_file='variables_druid_dev'
                        if self.aws_region == 'us-east-1':
                            self.environment_variables_from_secret='dev-us-druid-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.environment_variables_from_secret='dev-eu-druid-secrets'
                    elif self.level == 'stage':
                        if 'druid-query-stage-1' == self.env:
                            self.local_variables_file_1=f'variables_druid_router_1_stage_1'
                            self.local_variables_file_2=f'variables_druid_broker_1_stage_1'
                        elif 'druid-query-2-stage-1' == self.env:
                            self.local_variables_file_1=f'variables_druid_router_2_stage_1'
                            self.local_variables_file_2=f'variables_druid_broker_2_stage_1'
                        elif 'druid-query-stage-2' == self.env:
                            self.local_variables_file_1=f'variables_druid_router_1_stage_2'
                            self.local_variables_file_2=f'variables_druid_broker_1_stage_2'
                        elif 'druid-query-2-stage-2' == self.env:
                            self.local_variables_file_1=f'variables_druid_router_2_stage_2'
                            self.local_variables_file_2=f'variables_druid_broker_2_stage_2'
                        elif 'druid-query-stage-3' == self.env:
                            self.local_variables_file_1=f'variables_druid_router_1_stage_3'
                            self.local_variables_file_2=f'variables_druid_broker_1_stage_3'
                        elif 'druid-query-2-stage-3' == self.env:
                            self.local_variables_file_1=f'variables_druid_router_2_stage_3'
                            self.local_variables_file_2=f'variables_druid_broker_2_stage_3'
                        elif 'druid-query-stage-4' == self.env:
                            self.local_variables_file_1=f'variables_druid_router_1_stage_4'
                            self.local_variables_file_2=f'variables_druid_broker_1_stage_4'
                        elif 'druid-query-2-stage-4' == self.env:
                            self.local_variables_file_1=f'variables_druid_router_2_stage_4'
                            self.local_variables_file_2=f'variables_druid_broker_2_stage_4'
                        elif 'druid-query-ops-1' == self.env:
                            self.local_variables_file_1=f'variables_druid_router_1_ops_1'
                            self.local_variables_file_2=f'variables_druid_broker_1_ops_1'
                        elif 'druid-query-2-ops-1' == self.env:
                            self.local_variables_file_1=f'variables_druid_router_2_ops_1'
                            self.local_variables_file_2=f'variables_druid_broker_2_ops_1'
                        elif 'druid-query-qa-1' == self.env:
                            self.local_variables_file_1=f'variables_druid_router_1_qa_1'
                            self.local_variables_file_2=f'variables_druid_broker_1_qa_1'
                        elif 'druid-query-2-qa-1' == self.env:
                            self.local_variables_file_1=f'variables_druid_router_2_qa_1'
                            self.local_variables_file_2=f'variables_druid_broker_2_qa_1'
                        elif 'druid-query-qa-2' == self.env:
                            self.local_variables_file_1=f'variables_druid_router_1_qa_2'
                            self.local_variables_file_2=f'variables_druid_broker_1_qa_2'
                        elif 'druid-query-2-qa-2' == self.env:
                            self.local_variables_file_1=f'variables_druid_router_2_qa_2'
                            self.local_variables_file_2=f'variables_druid_broker_2_qa_2'
                        elif 'druid-query-stage-eu-1' == self.env:
                            self.local_variables_file_1=f'variables_druid_router_1_stage_eu_1'
                            self.local_variables_file_2=f'variables_druid_broker_1_stage_eu_1'
                        elif 'druid-query-2-stage-eu-1' == self.env:
                            self.local_variables_file_1=f'variables_druid_router_2_stage_eu_1'
                            self.local_variables_file_2=f'variables_druid_broker_2_stage_eu_1'
                        if self.aws_region == 'us-east-1':
                            self.environment_variables_from_secret='stage-us-druid-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.environment_variables_from_secret='stage-eu-druid-secrets'
                    elif self.level == 'prod':
                        if self.aws_region == 'us-east-1':
                            self.environment_variables_from_secret='prod-us-druid-secrets'
                            if 'druid-query-prod-us-1' == self.env:
                                self.local_variables_file_1=f'variables_druid_router_prod_us_1'
                                self.local_variables_file_2=f'variables_druid_broker_prod_us_1'
                            elif 'druid-query-prod-us-2' == self.env:
                                self.local_variables_file_1=f'variables_druid_router_prod_us_2'
                                self.local_variables_file_2=f'variables_druid_broker_prod_us_2'
                        elif self.aws_region == 'eu-west-1':
                            self.environment_variables_from_secret='prod-eu-druid-secrets'
                            if 'druid-query-prod-eu-1' == self.env:
                                self.local_variables_file_1=f'variables_druid_router_prod_eu_1'
                                self.local_variables_file_2=f'variables_druid_broker_prod_eu_1'
                            elif 'druid-query-prod-eu-2' == self.env:
                                self.local_variables_file_1=f'variables_druid_router_prod_eu_2'
                                self.local_variables_file_2=f'variables_druid_broker_prod_eu_2'
                else:
                    self.default_env_variables='env.druid.example'
                    if self.level == 'dev':
                        self.environment_variables_from_secret=''
                    elif self.level == 'prod':
                        self.environment_variables_from_secret=f'{self.env}-router-vars'
                    else:
                        if 'druid-query-stage-1' == self.env:
                            self.environment_variables_from_secret=f'druid-query-stage-1-router-vars'
                        elif 'druid-query-2-stage-1' == self.env:
                            self.environment_variables_from_secret=f'druid-query-2-stage-1-router-vars'
                        elif 'druid-query-stage-2' == self.env:
                            self.environment_variables_from_secret=f'druid-query-stage-2-router-vars'
                        elif 'druid-query-2-stage-2' == self.env:
                            self.environment_variables_from_secret=f'druid-query-2-stage-2-router-vars'
                        elif 'druid-query-stage-3' == self.env:
                            self.environment_variables_from_secret=f'druid-query-stage-3-router-vars'
                        elif 'druid-query-2-stage-3' == self.env:
                            self.environment_variables_from_secret=f'druid-query-2-stage-3-router-vars'
                        elif 'druid-query-stage-4' == self.env:
                            self.environment_variables_from_secret=f'druid-query-stage-4-router-vars'
                        elif 'druid-query-2-stage-4' == self.env:
                            self.environment_variables_from_secret=f'druid-query-2-stage-4-router-vars'
                        elif 'druid-query-ops-1' == self.env:
                            self.environment_variables_from_secret=f'druid-query-ops-1-router-vars'
                        elif 'druid-query-2-ops-1' == self.env:
                            self.environment_variables_from_secret=f'druid-query-2-ops-1-router-vars'
                        elif 'druid-query-qa-1' == self.env:
                            self.environment_variables_from_secret=f'druid-query-qa-1-router-vars'
                        elif 'druid-query-2-qa-1' == self.env:
                            self.environment_variables_from_secret=f'druid-query-2-qa-1-router-vars'
                        elif 'druid-query-qa-2' == self.env:
                            self.environment_variables_from_secret=f'druid-query-qa-2-router-vars'
                        elif 'druid-query-2-qa-2' == self.env:
                            self.environment_variables_from_secret=f'druid-query-2-qa-2-router-vars'
                        elif 'druid-query-prod-us-1' == self.env:
                            self.environment_variables_from_secret=f'druid-query-prod-us-1-router-vars'
                        elif 'druid-query-2-prod-us-1' == self.env:
                            self.environment_variables_from_secret=f'druid-query-2-prod-us-1-router-vars'
                        elif 'druid-query-prod-eu-1' == self.env:
                            self.environment_variables_from_secret=f'druid-query-prod-eu-1-router-vars'
                        elif 'druid-query-2-prod-eu-1' == self.env:
                            self.environment_variables_from_secret=f'druid-query-2-prod-eu-1-router-vars'
                        elif 'druid-query-stage-eu-1' == self.env:
                            self.environment_variables_from_secret=f'druid-query-stage-eu-1-router-vars'
                        elif 'druid-query-2-stage-eu-1' == self.env:
                            self.environment_variables_from_secret=f'druid-query-2-stage-eu-1-router-vars'

                if 'prod-us' in self.env:
                    self.aws_logs_group='metrix-prod'
                elif 'prod-eu' in self.env:
                    self.aws_logs_group='metrix-prod'
                else:
                    self.aws_logs_group='metrix'

                self.druid_user=return_secret_value_from_sm(
                                                                secret_name=self.environment_variables_from_secret, 
                                                                region=self.aws_region, 
                                                                secret_to_return='druid_escalator_internalClientUsernam')
                self.druid_password=return_secret_value_from_sm(
                                                                secret_name=self.environment_variables_from_secret, 
                                                                region=self.aws_region, 
                                                                secret_to_return='druid_escalator_internalClientPassword')

                self.url=self.add_credentials(self.druid_user, self.druid_password)

                if os.path.exists(self.source_code):
                    self.version=f'{self.get_git_branch(self.source_code).replace("/", "_")}_{self.get_git_hash(self.source_code)}'
                else:
                    print_log_message(log_level='ERROR', msg=f'Missing source coede {self.source_code}')
                    sys.exit(1)
                self.tag=f'{self.default_ecr_registry}/{self.docker_image_name}:{self.version}'
                self.docker_build_command=f'''docker build \
                                                --build-arg log4j_version={self.metrix_log4j_version} \
                                                -t {self.tag} -f {self.dockerfile_name} .  --progress plain --network=host {self.no_cache}'''
            ######################################################################################################################################################
            case 'metrix-druid-data':
                self.product_name='metrix-druid-data'
                self.source_code=f'{self.source_code_path}/data_pipeline'
                self.path_to_dockerfile=f'{self.source_code}/druid-docker/druid'
                self.dockerfile_name='Dockerfile'
                self.docker_image_name="metrix-druid"
                self.docker_buildargs={}
                self.code_build_command=""
                self.env_vars_chech_enabled=True
                self.deployment_bucket_dir=f'metrix_druid_data'
                self.expected_health_check_response_code=response_code
                self.branch_name_variable_jenkins='METRIX_BRANCH_NAME'

                self.list_of_files_to_update_creds=[
                    f'{self.source_code}/druid-docker/druid/Dockerfile_druid',
                ]

                if template_dir == '':
                    self.template_location=f'{self.templates_base_dir}/druid_metrix'
                else:
                    self.template_location=f'{self.templates_base_dir}/{template_dir}'
                if template_name == '':
                    self.template_name="druid-data-dc-localvars.yaml.j2"
                else:
                    self.template_name=template_name

                if self.use_local_variables_file:
                    self.default_env_variables='deployments/druid_secrets'
                    self.local_variables_dir=f'{self.source_code}/deployments'
                    if self.level == 'dev':
                        self.local_variables_file='variables_druid_dev'
                        if self.aws_region == 'us-east-1':
                            self.environment_variables_from_secret='dev-us-druid-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.environment_variables_from_secret='dev-eu-druid-secrets'
                    elif self.level == 'stage':
                        if 'druid-data-stage-1' == self.env:
                            self.local_variables_file_1=f'variables_druid_historical_1_stage_1'
                            self.local_variables_file_2=f'variables_druid_middlemanager_1_stage_1'
                        elif 'druid-data-2-stage-1' == self.env:
                            self.local_variables_file_1=f'variables_druid_historical_2_stage_1'
                            self.local_variables_file_2=f'variables_druid_middlemanager_2_stage_1'
                        elif 'druid-data-stage-2' == self.env:
                            self.local_variables_file_1=f'variables_druid_historical_1_stage_2'
                            self.local_variables_file_2=f'variables_druid_middlemanager_1_stage_2'
                        elif 'druid-data-2-stage-2' == self.env:
                            self.local_variables_file_1=f'variables_druid_historical_2_stage_2'
                            self.local_variables_file_2=f'variables_druid_middlemanager_2_stage_2'
                        elif 'druid-data-stage-3' == self.env:
                            self.local_variables_file_1=f'variables_druid_historical_1_stage_3'
                            self.local_variables_file_2=f'variables_druid_middlemanager_1_stage_3'
                        elif 'druid-data-2-stage-3' == self.env:
                            self.local_variables_file_1=f'variables_druid_historical_2_stage_3'
                            self.local_variables_file_2=f'variables_druid_middlemanager_2_stage_3'
                        elif 'druid-data-stage-4' == self.env:
                            self.local_variables_file_1=f'variables_druid_historical_1_stage_4'
                            self.local_variables_file_2=f'variables_druid_middlemanager_1_stage_4'
                        elif 'druid-data-2-stage-4' == self.env:
                            self.local_variables_file_1=f'variables_druid_historical_2_stage_4'
                            self.local_variables_file_2=f'variables_druid_middlemanager_2_stage_4'
                        elif 'druid-data-ops-1' == self.env:
                            self.local_variables_file_1=f'variables_druid_historical_1_ops_1'
                            self.local_variables_file_2=f'variables_druid_middlemanager_1_ops_1'
                        elif 'druid-data-2-ops-1' == self.env:
                            self.local_variables_file_1=f'variables_druid_historical_2_ops_1'
                            self.local_variables_file_2=f'variables_druid_middlemanager_2_ops_1'
                        elif 'druid-data-qa-1' == self.env:
                            self.local_variables_file_1=f'variables_druid_historical_1_qa_1'
                            self.local_variables_file_2=f'variables_druid_middlemanager_1_qa_1'
                        elif 'druid-data-2-qa-1' == self.env:
                            self.local_variables_file_1=f'variables_druid_historical_2_qa_1'
                            self.local_variables_file_2=f'variables_druid_middlemanager_2_qa_1'
                        elif 'druid-data-qa-2' == self.env:
                            self.local_variables_file_1=f'variables_druid_historical_1_qa_2'
                            self.local_variables_file_2=f'variables_druid_middlemanager_1_qa_2'
                        elif 'druid-data-2-qa-2' == self.env:
                            self.local_variables_file_1=f'variables_druid_historical_2_qa_2'
                            self.local_variables_file_2=f'variables_druid_middlemanager_2_qa_2'
                        elif 'druid-data-stage-eu-1' == self.env:
                            self.local_variables_file_1=f'variables_druid_historical_1_stage_eu_1'
                            self.local_variables_file_2=f'variables_druid_middlemanager_1_stage_eu_1'
                        elif 'druid-data-2-stage-eu-1' == self.env:
                            self.local_variables_file_1=f'variables_druid_historical_2_stage_eu_1'
                            self.local_variables_file_2=f'variables_druid_middlemanager_2_stage_eu_1'
                        if self.aws_region == 'us-east-1':
                            self.environment_variables_from_secret='stage-us-druid-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.environment_variables_from_secret='stage-eu-druid-secrets'
                    elif self.level == 'prod':
                        if self.aws_region == 'us-east-1':
                            self.environment_variables_from_secret='prod-us-druid-secrets'
                            if 'druid-data-prod-us-1' == self.env:
                                self.local_variables_file_1=f'variables_druid_historical_prod_us_1'
                                self.local_variables_file_2=f'variables_druid_middlemanager_prod_us_1'
                            elif 'druid-data-prod-us-2' == self.env:
                                self.local_variables_file_1=f'variables_druid_historical_prod_us_2'
                                self.local_variables_file_2=f'variables_druid_middlemanager_prod_us_2'
                            elif 'druid-data-prod-us-3' == self.env:
                                self.local_variables_file_1=f'variables_druid_historical_prod_us_3'
                                self.local_variables_file_2=f'variables_druid_middlemanager_prod_us_3'
                        elif self.aws_region == 'eu-west-1':
                            self.environment_variables_from_secret='prod-eu-druid-secrets'
                            if 'druid-data-prod-eu-1' == self.env:
                                self.local_variables_file_1=f'variables_druid_historical_prod_eu_1'
                                self.local_variables_file_2=f'variables_druid_middlemanager_prod_eu_1'
                            elif 'druid-data-prod-eu-2' == self.env:
                                self.local_variables_file_1=f'variables_druid_historical_prod_eu_2'
                                self.local_variables_file_2=f'variables_druid_middlemanager_prod_eu_2'
                            elif 'druid-data-prod-eu-3' == self.env:
                                self.local_variables_file_1=f'variables_druid_historical_prod_eu_3'
                                self.local_variables_file_2=f'variables_druid_middlemanager_prod_eu_3'
                else:
                    self.default_env_variables='env.druid.example'
                    if self.level == 'dev':
                        self.environment_variables_from_secret=''
                    elif self.level == 'prod':
                        self.environment_variables_from_secret=f'{self.env}-historical-vars'
                    else:
                        if 'druid-data-stage-1' == self.env:
                            self.environment_variables_from_secret=f'druid-data-stage-1-historical-vars'
                        elif 'druid-data-2-stage-1' == self.env:
                            self.environment_variables_from_secret=f'druid-data-2-stage-1-historical-vars'
                        elif 'druid-data-stage-2' == self.env:
                            self.environment_variables_from_secret=f'druid-data-stage-2-historical-vars'
                        elif 'druid-data-2-stage-2' == self.env:
                            self.environment_variables_from_secret=f'druid-data-2-stage-2-historical-vars'
                        elif 'druid-data-stage-3' == self.env:
                            self.environment_variables_from_secret=f'druid-data-stage-3-historical-vars'
                        elif 'druid-data-2-stage-3' == self.env:
                            self.environment_variables_from_secret=f'druid-data-2-stage-3-historical-vars'
                        elif 'druid-data-stage-4' == self.env:
                            self.environment_variables_from_secret=f'druid-data-stage-4-historical-vars'
                        elif 'druid-data-2-stage-4' == self.env:
                            self.environment_variables_from_secret=f'druid-data-2-stage-4-historical-vars'
                        elif 'druid-data-ops-1' == self.env:
                            self.environment_variables_from_secret=f'druid-data-ops-1-historical-vars'
                        elif 'druid-data-2-ops-1' == self.env:
                            self.environment_variables_from_secret=f'druid-data-2-ops-1-historical-vars'
                        elif 'druid-data-qa-1' == self.env:
                            self.environment_variables_from_secret=f'druid-data-qa-1-historical-vars'
                        elif 'druid-data-2-qa-1' == self.env:
                            self.environment_variables_from_secret=f'druid-data-2-qa-1-historical-vars'
                        elif 'druid-data-qa-2' == self.env:
                            self.environment_variables_from_secret=f'druid-data-qa-2-historical-vars'
                        elif 'druid-data-2-qa-2' == self.env:
                            self.environment_variables_from_secret=f'druid-data-2-qa-2-historical-vars'
                        elif 'druid-data-prod-us-1' == self.env:
                            self.environment_variables_from_secret=f'druid-data-prod-us-1-historical-vars'
                        elif 'druid-data-2-prod-us-1' == self.env:
                            self.environment_variables_from_secret=f'druid-data-2-prod-us-1-historical-vars'
                        elif 'druid-data-prod-eu-1' == self.env:
                            self.environment_variables_from_secret=f'druid-data-prod-eu-1-historical-vars'
                        elif 'druid-data-2-prod-eu-1' == self.env:
                            self.environment_variables_from_secret=f'druid-data-2-prod-eu-1-historical-vars'
                        elif 'druid-data-stage-eu-1' == self.env:
                            self.environment_variables_from_secret=f'druid-data-stage-eu-1-historical-vars'
                        elif 'druid-data-2-stage-eu-1' == self.env:
                            self.environment_variables_from_secret=f'druid-data-2-stage-eu-1-historical-vars'

                if 'prod-us' in self.env:
                    self.aws_logs_group='metrix-prod'
                elif 'prod-eu' in self.env:
                    self.aws_logs_group='metrix-prod'
                else:
                    self.aws_logs_group='metrix'

                self.druid_user=return_secret_value_from_sm(
                                                                secret_name=self.environment_variables_from_secret, 
                                                                region=self.aws_region, 
                                                                secret_to_return='druid_escalator_internalClientUsernam')
                self.druid_password=return_secret_value_from_sm(
                                                                secret_name=self.environment_variables_from_secret, 
                                                                region=self.aws_region, 
                                                                secret_to_return='druid_escalator_internalClientPassword')

                self.url=self.add_credentials(self.druid_user, self.druid_password)

                if os.path.exists(self.source_code):
                    self.version=f'{self.get_git_branch(self.source_code).replace("/", "_")}_{self.get_git_hash(self.source_code)}'
                else:
                    print_log_message(log_level='ERROR', msg=f'Missing source coede {self.source_code}')
                    sys.exit(1)
                self.tag=f'{self.default_ecr_registry}/{self.docker_image_name}:{self.version}'
                self.docker_build_command=f'''docker build \
                                                --build-arg log4j_version={self.metrix_log4j_version} \
                                                -t {self.tag} -f {self.dockerfile_name} .  --progress plain --network=host {self.no_cache}'''
            ######################################################################################################################################################
            case 'metrix-druid':
                self.product_name='metrix-druid'
                self.source_code=f'{self.source_code_path}/data_pipeline'
                self.path_to_dockerfile=f'{self.source_code}/druid-docker/druid'
                self.dockerfile_name='Dockerfile'
                self.docker_image_name=self.product_name
                self.docker_buildargs={}
                self.code_build_command=""
                self.env_vars_chech_enabled=True
                self.deployment_bucket_dir=f'metrix_druid'
                self.expected_health_check_response_code=response_code
                self.branch_name_variable_jenkins='METRIX_BRANCH_NAME'
                
                self.list_of_files_to_update_creds=[
                    f'{self.source_code}/druid-docker/druid/Dockerfile_druid',
                ]

                if template_dir == '':
                    self.template_location=f'{self.templates_base_dir}/druid_metrix'
                else:
                    self.template_location=f'{self.templates_base_dir}/{template_dir}'
                if template_name == '':
                    self.template_name="druid-dc-localvars.yaml.j2"
                else:
                    self.template_name=template_name

                if self.use_local_variables_file:
                    self.default_env_variables='deployments/druid_secrets'
                    self.local_variables_dir=f'{self.source_code}/deployments'
                    if self.level == 'dev':
                        self.local_variables_file='variables_druid_dev'
                        if self.aws_region == 'us-east-1':
                            self.environment_variables_from_secret='dev-us-druid-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.environment_variables_from_secret='dev-eu-druid-secrets'
                    else:
                        self.environment_variables_from_secret=''
                else: 
                    self.default_env_variables='env.druid.example'
                    if self.level == 'dev':
                        self.environment_variables_from_secret=f'local-{self.env}-druid-secrets'
                    else:
                        self.environment_variables_from_secret=f''

                if 'prod-us' in self.env:
                    self.aws_logs_group='metrix-prod'
                elif 'prod-eu' in self.env:
                    self.aws_logs_group='metrix-prod'
                else:
                    self.aws_logs_group='metrix'

                self.druid_user=return_secret_value_from_sm(
                                                                secret_name=self.environment_variables_from_secret, 
                                                                region=self.aws_region, 
                                                                secret_to_return='druid_escalator_internalClientUsernam')
                self.druid_password=return_secret_value_from_sm(
                                                                secret_name=self.environment_variables_from_secret, 
                                                                region=self.aws_region, 
                                                                secret_to_return='druid_escalator_internalClientPassword')

                self.url=self.add_credentials(self.druid_user, self.druid_password)

                if os.path.exists(self.source_code):
                    self.version=f'{self.get_git_branch(self.source_code).replace("/", "_")}_{self.get_git_hash(self.source_code)}'
                else:
                    print_log_message(log_level='ERROR', msg=f'Missing source coede {self.source_code}')
                    sys.exit(1)
                self.tag=f'{self.default_ecr_registry}/{self.docker_image_name}:{self.version}'
                self.docker_build_command=f'''docker build \
                                                --build-arg log4j_version={self.metrix_log4j_version} \
                                                -t {self.tag} -f {self.dockerfile_name} .  --progress plain --network=host {self.no_cache}'''
            ######################################################################################################################################################
            case 'metrix-spark':
                self.product_name='metrix-spark'
                self.source_code=f'{self.source_code_path}/data_pipeline'
                self.path_to_dockerfile=f'{self.source_code}/spark-docker/spark'
                self.dockerfile_name='Dockerfile'
                self.docker_image_name="metrix-spark"
                self.docker_buildargs={}
                self.code_build_command=""
                self.env_vars_chech_enabled=True
                self.default_env_variables='env.example'
                self.deployment_bucket_dir=f'metrix_spark'
                self.branch_name_variable_jenkins='METRIX_BRANCH_NAME'
                self.expected_health_check_response_code=response_code
                
                self.list_of_files_to_update_creds=[
                    f'{self.source_code}/artifactory-secret.example/netrc.template',
                    f'{self.source_code}/artifactory-secret.example/pip.conf',
                    f'{self.source_code}/artifactory-secret.example/sources.list',
                ]

                if template_dir == '':
                    self.template_location=f'{self.templates_base_dir}/metrix_spark'
                else:
                    self.template_location=f'{self.templates_base_dir}/{template_dir}'
                if template_name == '':
                    self.template_name="spark-dc-localvars.yml.j2"
                else:
                    self.template_name=template_name

                if self.use_local_variables_file:
                    self.default_env_variables='spark-docker/spark/deployments/secrets'
                    self.local_variables_dir=f'{self.source_code}/deployments'
                    if self.level == 'dev':
                        self.local_variables_file='variables_spark_dev'
                        if self.aws_region == 'us-east-1':
                            self.environment_variables_from_secret=''
                        elif self.aws_region == 'eu-west-1':
                            self.environment_variables_from_secret=''
                    else:
                        self.local_variables_file=''
                        self.environment_variables_from_secret=''
                else:
                    if self.level == 'dev':
                        self.environment_variables_from_secret=''
                    else:
                        self.environment_variables_from_secret=''

                if 'prod-us' in self.env:
                    self.aws_logs_group='metrix-prod'
                elif 'prod-eu' in self.env:
                    self.aws_logs_group='metrix-prod'
                else:
                    self.aws_logs_group='metrix'

                if os.path.exists(self.source_code):
                    self.version=f'{self.get_git_branch(self.source_code).replace("/", "_")}_{self.get_git_hash(self.source_code)}'
                else:
                    print_log_message(log_level='ERROR', msg=f'Missing source coede {self.source_code}')
                    sys.exit(1)
                self.tag=f'{self.default_ecr_registry}/{self.docker_image_name}:{self.version}'

                self.docker_build_command=f'''DOCKER_BUILDKIT=1 docker build \
                                                --secret id=apt,src={self.source_code}/artifactory-secret.example/sources.list \
                                                --secret id=netrc,src={self.source_code}/artifactory-secret.example/netrc.template \
                                                --secret id=pip,src={self.source_code}/artifactory-secret.example/pip.conf \
                                                --build-arg mode=dev \
                                                -t {self.tag} -f {self.dockerfile_name} .  --progress plain --network=host {self.no_cache}'''
            ######################################################################################################################################################
            case 'order-service':
                self.product_name='order-service'
                self.source_code=f'{self.source_code_path}/order-service'
                self.path_to_dockerfile=f'{self.source_code}'
                self.dockerfile_name='Dockerfile'
                self.docker_image_name="order-service"
                self.docker_buildargs={}
                self.code_build_command=""
                self.env_vars_chech_enabled=True
                self.deployment_bucket_dir=f'order_service'
                self.branch_name_variable_jenkins='ORDER_SERVICE_BRANCH_NAME'
                self.expected_health_check_response_code=response_code
                
                self.list_of_files_to_update_creds=[
                    f'{self.source_code}/maven-settings.xml'
                ]

                
                if template_dir == '':
                    self.template_location=f'{self.templates_base_dir}/order_service'
                else:
                    self.template_location=f'{self.templates_base_dir}/{template_dir}'
                if template_name == '':
                    self.template_name="order-service-dc-localvars.yml.j2"
                else:
                    self.template_name=template_name

                if self.use_local_variables_file:
                    self.default_env_variables='deployments/secrets'
                    self.local_variables_dir=f'{self.source_code}/deployments'
                    if self.level == 'dev':
                        self.local_variables_file='variables_dev'
                        if self.aws_region == 'us-east-1':
                            self.environment_variables_from_secret='dev-us-order-service-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.environment_variables_from_secret='dev-eu-order-service-secrets'
                    elif self.level == 'stage':
                        self.local_variables_file='variables_stage'
                        if self.aws_region == 'us-east-1':
                            self.environment_variables_from_secret='stage-us-order-service-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.environment_variables_from_secret='stage-eu-order-service-secrets'
                    elif self.level == 'prod':
                        if self.aws_region == 'us-east-1':
                            self.local_variables_file='variables_prod_us'
                            self.environment_variables_from_secret='prod-us-order-service-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.local_variables_file='variables_prod_eu'
                            self.environment_variables_from_secret='prod-eu-order-service-secrets'
                else: 
                    self.default_env_variables='env.example'
                    if self.level == 'dev':
                        self.environment_variables_from_secret=f'local-{self.env}-order-service-secrets'
                    else:
                        self.environment_variables_from_secret=f'{self.env}-vars'

                if 'prod-us' in self.env:
                    self.aws_logs_group='java-prod-us'
                elif 'prod-eu' in self.env:
                    self.aws_logs_group='java-prod-eu'
                else:
                    self.aws_logs_group='java_instances_stage'

                if os.path.exists(self.source_code):
                    self.version=f'{self.get_git_branch(self.source_code).replace("/", "_")}_{self.get_git_hash(self.source_code)}'
                else:
                    print_log_message(log_level='ERROR', msg=f'Missing source coede {self.source_code}')
                    sys.exit(1)
                self.tag=f'{self.default_ecr_registry}/{self.docker_image_name}:{self.version}'

                self.docker_build_command=f'''DOCKER_BUILDKIT=1 docker build \
                                                --build-arg USB_USER={self.user} \
                                                --build-arg USB_PASS={self.password} \
                                                --build-arg USB_PROXY_URL={self.proxy} \
                                                -t {self.tag} -f {self.dockerfile_name} .  --progress plain --network=host {self.no_cache}'''
            ######################################################################################################################################################
            case 'file-service':
                self.product_name='file-service'
                self.source_code=f'{self.source_code_path}/file_service'
                self.path_to_dockerfile=f'{self.source_code}'
                self.dockerfile_name='Dockerfile_fileservice'
                self.docker_image_name="file-service"
                self.docker_buildargs={}
                self.code_build_command="build_file_service.sh fileservice"
                self.env_vars_chech_enabled=True
                self.deployment_bucket_dir=f'file_service'
                self.branch_name_variable_jenkins='FILE_SERVICE_BRANCH_NAME'
                self.expected_health_check_response_code=response_code
                
                self.list_of_files_to_update_creds=[
                    f'{self.source_code}/docker_build_files/settings.xml',
                ]

                if template_dir == '':
                    self.template_location=f'{self.templates_base_dir}/file_service'
                else:
                    self.template_location=f'{self.templates_base_dir}/{template_dir}'
                if template_name == '':
                    self.template_name="file-service-dc-localvars.yml.j2"
                else:
                    self.template_name=template_name

                if self.use_local_variables_file:
                    self.default_env_variables='deployments/secrets'
                    self.local_variables_dir=f'{self.source_code}/deployments'
                    if self.level == 'dev':
                        self.local_variables_file='variables_dev'
                        if self.aws_region == 'us-east-1':
                            self.environment_variables_from_secret='dev-us-file-service-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.environment_variables_from_secret='dev-eu-file-service-secrets'
                    elif self.level == 'stage':
                        self.local_variables_file='variables_stage'
                        if self.aws_region == 'us-east-1':
                            self.environment_variables_from_secret='stage-us-file-service-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.environment_variables_from_secret='stage-eu-file-service-secrets'
                    elif self.level == 'prod':
                        if self.aws_region == 'us-east-1':
                            self.local_variables_file='variables_prod_us'
                            self.environment_variables_from_secret='prod-us-file-service-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.local_variables_file='variables_prod_eu'
                            self.environment_variables_from_secret='prod-eu-file-service-secrets'
                else: 
                    self.default_env_variables='env.example'
                    if self.level == 'dev':
                        self.environment_variables_from_secret=f'local-{self.env}-file-service-secrets'
                    else:
                        self.environment_variables_from_secret=f'{self.env}-vars'

                if 'prod-us' in self.env:
                    self.aws_logs_group='java-prod-us'
                elif 'prod-eu' in self.env:
                    self.aws_logs_group='java-prod-eu'
                else:
                    self.aws_logs_group='java_instances_stage'

                if os.path.exists(self.source_code):
                    self.version=f'{self.get_git_branch(self.source_code).replace("/", "_")}_{self.get_git_hash(self.source_code)}'
                else:
                    print_log_message(log_level='ERROR', msg=f'Missing source coede {self.source_code}')
                    sys.exit(1)
                self.tag=f'{self.default_ecr_registry}/{self.docker_image_name}:{self.version}'

                self.docker_build_command=f'''DOCKER_BUILDKIT=0 docker build \
                                                -t {self.tag} -f {self.dockerfile_name} .  --progress plain --network=host {self.no_cache}'''
            ######################################################################################################################################################
            case 'iai-cron-feature':
                self.product_name='iai-cron-feature'
                product_name_underscore=self.product_name.replace('-', '_')
                self.source_code=f'{self.source_code_path}/imports_and_integrations'
                self.path_to_dockerfile=f'{self.source_code}/airflow_feature'
                self.dockerfile_name='Dockerfile_airflow'
                self.docker_image_name="iai-cron-feature"
                self.docker_buildargs={}
                self.code_build_command=""
                self.env_vars_chech_enabled=True
                
                self.deployment_bucket_dir=f'iai_cron_feature'
                self.branch_name_variable_jenkins='IMPORTS_AND_INTEGRATIONS_BRANCH_NAME'
                self.expected_health_check_response_code=response_code
                
                self.list_of_files_to_update_creds=[
                    f'{self.source_code}/airflow_feature/docker/pip.conf'
                ]

                if template_dir == '':
                    self.template_location=f'{self.templates_base_dir}/iai_cron_feature'
                else:
                    self.template_location=f'{self.templates_base_dir}/{template_dir}'
                if template_name == '':
                    self.template_name="iai-cron-feature-dc-localvars.yaml.j2"
                else:
                    self.template_name=template_name

                if self.use_local_variables_file:
                    self.default_env_variables='deployments/secrets'
                    self.local_variables_dir=f'{self.source_code}/deployments'
                    if self.level == 'dev':
                        self.local_variables_file=f'variables_{product_name_underscore}_dev'
                        if self.aws_region == 'us-east-1':
                            self.environment_variables_from_secret='dev-us-iai-cron-feature-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.environment_variables_from_secret='dev-eu-iai-cron-feature-secrets'
                    elif self.level == 'stage':
                        self.local_variables_file=f'variables_{product_name_underscore}_stage'
                        if self.aws_region == 'us-east-1':
                            self.environment_variables_from_secret='stage-us-iai-cron-feature-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.environment_variables_from_secret='stage-eu-iai-cron-feature-secrets'
                    elif self.level == 'prod':
                        if self.aws_region == 'us-east-1':
                            self.local_variables_file=f'variables_{product_name_underscore}_prod_us'
                            self.environment_variables_from_secret='prod-us-iai-cron-feature-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.local_variables_file=f'variables_{product_name_underscore}_prod_eu'
                            self.environment_variables_from_secret='prod-eu-iai-cron-feature-secrets'
                else: 
                    self.default_env_variables=f'{self.path_to_dockerfile}/env.example'
                    if self.level == 'dev':
                        self.environment_variables_from_secret=f'local-{self.env}-iai-cron-feature-secrets'
                    else:
                        self.environment_variables_from_secret=f'{self.env}-vars'

                if 'prod-us' in self.env:
                    self.aws_logs_group='iai-cron-feature-prod-us'
                elif 'prod-eu' in self.env:
                    self.aws_logs_group='iai-cron-feature-prod-eu'
                else:
                    self.aws_logs_group='iai-cron-feature-stage'

                if os.path.exists(self.source_code):
                    self.version=f'{self.get_git_branch(self.source_code).replace("/", "_")}_{self.get_git_hash(self.source_code)}'
                else:
                    print_log_message(log_level='ERROR', msg=f'Missing source coede {self.source_code}')
                    sys.exit(1)
                self.tag=f'{self.default_ecr_registry}/{self.docker_image_name}:{self.version}'

                self.docker_build_command=f'''DOCKER_BUILDKIT=1 docker build \
                                                 --secret id=pip_conf,src={self.path_to_dockerfile}/docker/pip.conf \
                                                -t {self.tag} -f {self.dockerfile_name} .  --progress plain --network=host {self.no_cache}'''
            ######################################################################################################################################################
            case 'iai-web-app-be':
                self.product_name='iai-web-app-be'
                product_name_underscore = self.product_name.replace('-', '_')
                self.source_code=f'{self.source_code_path}/imports_and_integrations'
                self.path_to_dockerfile=f'{self.source_code}/web_app_be'
                self.dockerfile_name='Dockerfile'
                self.docker_image_name="iai-web-app-be"
                self.docker_buildargs={}
                self.code_build_command=""
                self.env_vars_chech_enabled=True
                self.deployment_bucket_dir=f'iai_web_app_be'
                self.branch_name_variable_jenkins='IMPORTS_AND_INTEGRATIONS_BRANCH_NAME'
                self.expected_health_check_response_code=response_code
                
                self.list_of_files_to_update_creds=[
                    f'{self.source_code}/web_app_be/docker/pip.conf'
                ]

                if template_dir == '':
                    self.template_location=f'{self.templates_base_dir}/iai_web_app_be'
                else:
                    self.template_location=f'{self.templates_base_dir}/{template_dir}'
                if template_name == '':
                    self.template_name="iai-web-app-be-dc-localvars.yaml.j2"
                else:
                    self.template_name=template_name

                if self.use_local_variables_file:
                    self.default_env_variables='deployments/secrets'
                    self.local_variables_dir=f'{self.source_code}/deployments'
                    if self.level == 'dev':
                        self.local_variables_file=f'variables_{product_name_underscore}_dev'
                        if self.aws_region == 'us-east-1':
                            self.environment_variables_from_secret='dev-us-iai-web-app-be-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.environment_variables_from_secret='dev-eu-iai-web-app-be-secrets'
                    elif self.level == 'stage':
                        self.local_variables_file=f'variables_{product_name_underscore}_stage'
                        if self.aws_region == 'us-east-1':
                            self.environment_variables_from_secret='stage-us-iai-web-app-be-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.environment_variables_from_secret='stage-eu-iai-web-app-be-secrets'
                    elif self.level == 'prod':
                        if self.aws_region == 'us-east-1':
                            self.local_variables_file=f'variables_{product_name_underscore}_prod_us'
                            self.environment_variables_from_secret='prod-us-iai-web-app-be-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.local_variables_file=f'variables_{product_name_underscore}_prod_eu'
                            self.environment_variables_from_secret='prod-eu-iai-web-app-be-secrets'
                else: 
                    self.default_env_variables=f'{self.path_to_dockerfile}/env.example'
                    if self.level == 'dev':
                        self.environment_variables_from_secret=f'local-{self.env}-iai-web-app-be-secrets'
                    else:
                        self.environment_variables_from_secret=f'{self.env}-vars'

                if 'prod-us' in self.env:
                    self.aws_logs_group='iai-web-app-be-prod-us'
                elif 'prod-eu' in self.env:
                    self.aws_logs_group='iai-web-app-be-prod-eu'
                else:
                    self.aws_logs_group='iai-web-app-be-stage'

                if os.path.exists(self.source_code):
                    self.version=f'{self.get_git_branch(self.source_code).replace("/", "_")}_{self.get_git_hash(self.source_code)}'
                else:
                    print_log_message(log_level='ERROR', msg=f'Missing source coede {self.source_code}')
                    sys.exit(1)
                self.tag=f'{self.default_ecr_registry}/{self.docker_image_name}:{self.version}'

                self.docker_build_command=f'''DOCKER_BUILDKIT=1 docker build \
                                                 --secret id=pip_conf,src={self.path_to_dockerfile}/docker/pip.conf \
                                                -t {self.tag} -f {self.dockerfile_name} .  --progress plain --network=host {self.no_cache}'''
            ######################################################################################################################################################
            case 'iai-api-request-executor':
                self.product_name='iai-api-request-executor'
                product_name_underscore = self.product_name.replace('-', '_')
                self.source_code=f'{self.source_code_path}/imports_and_integrations'
                self.path_to_dockerfile=f'{self.source_code}/api_request_executor'
                self.dockerfile_name='Dockerfile'
                self.docker_image_name="iai-api-request-executor"
                self.docker_buildargs={}
                self.code_build_command=""
                self.env_vars_chech_enabled=True
                self.deployment_bucket_dir=f'iai_api_request_executor'
                self.branch_name_variable_jenkins='IMPORTS_AND_INTEGRATIONS_BRANCH_NAME'
                self.expected_health_check_response_code=response_code
                
                self.list_of_files_to_update_creds=[
                    f'{self.source_code}/api_request_executor/docker/pip.conf'
                ]

                if template_dir == '':
                    self.template_location=f'{self.templates_base_dir}/iai_api_request_executor'
                else:
                    self.template_location=f'{self.templates_base_dir}/{template_dir}'
                if template_name == '':
                    self.template_name="iai-api-request-executor-dc-localvars.yml.j2"
                else:
                    self.template_name=template_name

                if self.use_local_variables_file:
                    self.default_env_variables='deployments/secrets'
                    self.local_variables_dir=f'{self.source_code}/deployments'
                    if self.level == 'dev':
                        self.local_variables_file=f'variables_{product_name_underscore}_dev'
                        if self.aws_region == 'us-east-1':
                            self.environment_variables_from_secret='dev-us-iai-api-request-executor-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.environment_variables_from_secret='dev-eu-iai-api-request-executor-secrets'
                    elif self.level == 'stage':
                        self.local_variables_file=f'variables_{product_name_underscore}_stage'
                        if self.aws_region == 'us-east-1':
                            self.environment_variables_from_secret='stage-us-iai-api-request-executor-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.environment_variables_from_secret='stage-eu-iai-api-request-executor-secrets'
                    elif self.level == 'prod':
                        if self.aws_region == 'us-east-1':
                            self.local_variables_file=f'variables_{product_name_underscore}_prod_us'
                            self.environment_variables_from_secret='prod-us-iai-api-request-executor-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.local_variables_file=f'variables_{product_name_underscore}_prod_eu'
                            self.environment_variables_from_secret='prod-eu-iai-api-request-executor-secrets'
                else: 
                    self.default_env_variables='env.example'
                    if self.level == 'dev':
                        self.environment_variables_from_secret=f'local-{self.env}-iai-api-request-executor-secrets'
                    else:
                        self.environment_variables_from_secret=f'{self.env}-vars'

                if 'prod-us' in self.env:
                    self.aws_logs_group='iai-api-request-executor-prod-us'
                elif 'prod-eu' in self.env:
                    self.aws_logs_group='iai-api-request-executor-prod-eu'
                else:
                    self.aws_logs_group='iai-api-request-executor-stage'

                if os.path.exists(self.source_code):
                    self.version=f'{self.get_git_branch(self.source_code).replace("/", "_")}_{self.get_git_hash(self.source_code)}'
                else:
                    print_log_message(log_level='ERROR', msg=f'Missing source coede {self.source_code}')
                    sys.exit(1)
                self.tag=f'{self.default_ecr_registry}/{self.docker_image_name}:{self.version}'

                self.docker_build_command=f'''DOCKER_BUILDKIT=1 docker build \
                                                 --secret id=pip_conf,src={self.path_to_dockerfile}/docker/pip.conf \
                                                -t {self.tag} -f {self.dockerfile_name} .  --progress plain --network=host {self.no_cache}'''
            ######################################################################################################################################################
            case 'ts-service':
                self.product_name='ts-service'
                self.source_code=f'{self.source_code_path}/ts_service'
                self.path_to_dockerfile=f'{self.source_code}'
                self.dockerfile_name='Dockerfile'
                self.docker_image_name="ts-service"
                self.docker_buildargs={}
                self.code_build_command=""
                self.env_vars_chech_enabled=True
                self.deployment_bucket_dir=f'timesheets-service'
                self.branch_name_variable_jenkins='TS_SERVICE_BRANCH_NAME'
                self.expected_health_check_response_code=response_code

                self.list_of_files_to_update_creds=[
                    f'{self.source_code}/build/maven_settings_template.xml'
                ]

                if template_dir == '':
                    self.template_location=f'{self.templates_base_dir}/ts_service'
                else:
                    self.template_location=f'{self.templates_base_dir}/{template_dir}'
                if template_name == '':
                    self.template_name="ts-service-dc-localvars.yaml.j2"
                else:
                    self.template_name=template_name

                if self.use_local_variables_file:
                    self.default_env_variables='deployments/secrets'
                    self.local_variables_dir=f'{self.source_code}/deployments'
                    if self.level == 'dev':
                        self.local_variables_file='variables_dev'
                        if self.aws_region == 'us-east-1':
                            self.environment_variables_from_secret='dev-us-ts-service-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.environment_variables_from_secret='dev-eu-ts-service-secrets'
                    elif self.level == 'stage':
                        self.local_variables_file='variables_stage'
                        if self.aws_region == 'us-east-1':
                            self.environment_variables_from_secret='stage-us-ts-service-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.environment_variables_from_secret='stage-eu-ts-service-secrets'
                    elif self.level == 'prod':
                        if self.aws_region == 'us-east-1':
                            self.local_variables_file='variables_prod_us'
                            self.environment_variables_from_secret='prod-us-ts-service-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.local_variables_file='variables_prod_eu'
                            self.environment_variables_from_secret='prod-eu-ts-service-secrets'
                else: 
                    self.default_env_variables='env.example'
                    if self.level == 'dev':
                        self.environment_variables_from_secret=f'local-{self.env}-ts-service-secrets'
                    else:
                        self.environment_variables_from_secret=f'{self.env}-vars'

                if 'prod-us' in self.env:
                    self.aws_logs_group='java-prod-us'
                elif 'prod-eu' in self.env:
                    self.aws_logs_group='java-prod-eu'
                else:
                    self.aws_logs_group='java_instances_stage'

                if os.path.exists(self.source_code):
                    self.version=f'{self.get_git_branch(self.source_code).replace("/", "_")}_{self.get_git_hash(self.source_code)}'
                else:
                    print_log_message(log_level='ERROR', msg=f'Missing source coede {self.source_code}')
                    sys.exit(1)
                self.tag=f'{self.default_ecr_registry}/{self.docker_image_name}:{self.version}'
                # self.docker_build_command=f'''export DOCKER_IMAGE_NAME={self.docker_image_name} && 
                #                               export DOCKER_TAG={self.version} && 
                #                               bash build_talech.sh {self.product_name} &&
                #                               docker tag {self.docker_image_name}:{self.version} {self.tag}'''
                # self.docker_build_command=f'''DOCKER_BUILDKIT=1 docker build \
                #                                 --secret id=maven_settings,src={self.source_code}/build/maven_settings_template.xml \
                #                                 -t {self.tag} -f {self.dockerfile_name} .  --progress plain --network=host {self.no_cache}'''
                self.docker_build_command=f'''DOCKER_BUILDKIT=1 docker build \
                                                --build-arg USB_USER={self.user} \
                                                --build-arg USB_PASS={self.password} \
                                                --build-arg USB_PROXY_URL={self.proxy} \
                                                -t {self.tag} -f {self.dockerfile_name} .  --progress plain --network=host {self.no_cache}'''
            ######################################################################################################################################################
            case 'data-ops':
                self.product_name='data-ops'
                self.source_code=f'{self.source_code_path}/talech_data_ops'
                self.path_to_dockerfile=f'{self.source_code}/Airflow'
                self.dockerfile_name='Dockerfile'
                self.docker_image_name="data-ops"
                self.docker_buildargs={}
                self.code_build_command=""
                self.env_vars_chech_enabled=True
                self.deployment_bucket_dir=f'talech_data_ops'
                self.branch_name_variable_jenkins='DATA_OPS_BRANCH_NAME'
                self.expected_health_check_response_code=response_code
                
                self.list_of_files_to_update_creds=[
                ]

                if template_dir == '':
                    self.template_location=f'{self.templates_base_dir}/data_ops'
                else:
                    self.template_location=f'{self.templates_base_dir}/{template_dir}'
                if template_name == '':
                    self.template_name="data-ops-dc-localvars.yaml.j2"
                else:
                    self.template_name=template_name

                if self.use_local_variables_file:
                    self.default_env_variables='deployments/secrets'
                    self.local_variables_dir=f'{self.source_code}/deployments'
                    if self.level == 'dev':
                        self.local_variables_file='variables_dev'
                        if self.aws_region == 'us-east-1':
                            self.environment_variables_from_secret=''
                        elif self.aws_region == 'eu-west-1':
                            self.environment_variables_from_secret=''
                    elif self.level == 'stage':
                        self.local_variables_file='variables_stage'
                        if self.aws_region == 'us-east-1':
                            self.environment_variables_from_secret=''
                        elif self.aws_region == 'eu-west-1':
                            self.environment_variables_from_secret=''
                    elif self.level == 'prod':
                        if self.aws_region == 'us-east-1':
                            self.local_variables_file='variables_prod_us'
                            self.environment_variables_from_secret=''
                        elif self.aws_region == 'eu-west-1':
                            self.local_variables_file='variables_prod_eu'
                            self.environment_variables_from_secret=''
                else: 
                    self.default_env_variables='env.example'
                    if self.level == 'dev':
                        self.environment_variables_from_secret=f'local-{self.env}-data-ops-secrets'
                    else:
                        self.environment_variables_from_secret=f'{self.env}-vars'

                if 'prod-us' in self.env:
                    self.aws_logs_group='java-prod-us'
                elif 'prod-eu' in self.env:
                    self.aws_logs_group='java-prod-eu'
                else:
                    self.aws_logs_group='java_instances_stage'

                if os.path.exists(self.source_code):
                    self.version=f'{self.get_git_branch(self.source_code).replace("/", "_")}_{self.get_git_hash(self.source_code)}'
                else:
                    print_log_message(log_level='ERROR', msg=f'Missing source coede {self.source_code}')
                    sys.exit(1)
                self.tag=f'{self.default_ecr_registry}/{self.docker_image_name}:{self.version}'

                self.docker_build_command=f'''DOCKER_BUILDKIT=0 docker build \
                                                -t {self.tag} -f {self.dockerfile_name} .  --progress plain --network=host {self.no_cache}'''
            ######################################################################################################################################################
            case 'invoice-service':
                self.product_name='invoice-service'
                self.source_code=f'{self.source_code_path}/invoice-service'
                self.path_to_dockerfile=f'{self.source_code}'
                self.dockerfile_name='Dockerfile'
                self.docker_image_name="invoice-service"
                self.docker_buildargs={}
                self.code_build_command=""
                self.env_vars_chech_enabled=True
                self.deployment_bucket_dir=f'invoice_service'
                self.branch_name_variable_jenkins='INVOICE_SERVICE_BRANCH_NAME'
                self.expected_health_check_response_code=response_code
                
                self.list_of_files_to_update_creds=[
                    f'{self.source_code}/maven-settings.xml'
                ]

                if template_dir == '':
                    self.template_location=f'{self.templates_base_dir}/invoice_service'
                else:
                    self.template_location=f'{self.templates_base_dir}/{template_dir}'
                if template_name == '':
                    self.template_name="invoice-service-dc-localvars.yaml.j2"
                else:
                    self.template_name=template_name

                if self.use_local_variables_file:
                    self.default_env_variables='deployments/secrets'
                    self.local_variables_dir=f'{self.source_code}/deployments'
                    if self.level == 'dev':
                        self.local_variables_file='variables_dev'
                        if self.aws_region == 'us-east-1':
                            self.environment_variables_from_secret='dev-us-invoice-service-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.environment_variables_from_secret='dev-eu-invoice-service-secrets'
                    elif self.level == 'stage':
                        self.local_variables_file='variables_stage'
                        if self.aws_region == 'us-east-1':
                            self.environment_variables_from_secret='stage-us-invoice-service-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.environment_variables_from_secret='stage-eu-invoice-service-secrets'
                    elif self.level == 'prod':
                        if self.aws_region == 'us-east-1':
                            self.local_variables_file='variables_prod_us'
                            self.environment_variables_from_secret='prod-us-invoice-service-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.local_variables_file='variables_prod_eu'
                            self.environment_variables_from_secret='prod-eu-invoice-service-secrets'
                else: 
                    self.default_env_variables='env.example'
                    if self.level == 'dev':
                        self.environment_variables_from_secret=f'local-{self.env}-micro-service-secrets'
                    else:
                        self.environment_variables_from_secret=f'{self.env}-vars'

                if 'prod-us' in self.env:
                    self.aws_logs_group='java-prod-us'
                elif 'prod-eu' in self.env:
                    self.aws_logs_group='java-prod-eu'
                else:
                    self.aws_logs_group='java_instances_stage'

                if os.path.exists(self.source_code):
                    self.version=f'{self.get_git_branch(self.source_code).replace("/", "_")}_{self.get_git_hash(self.source_code)}'
                else:
                    print_log_message(log_level='ERROR', msg=f'Missing source coede {self.source_code}')
                    sys.exit(1)
                self.tag=f'{self.default_ecr_registry}/{self.docker_image_name}:{self.version}'

                self.docker_build_command=f'''DOCKER_BUILDKIT=1 docker build \
                                                --build-arg USB_USER={self.user} \
                                                --build-arg USB_PASS={self.password} \
                                                --build-arg USB_PROXY_URL={self.proxy} \
                                                -t {self.tag} -f {self.dockerfile_name} .  --progress plain --network=host {self.no_cache}'''
            ######################################################################################################################################################
            case 'iai-cron':
                self.product_name='iai-cron'
                product_name_underscore = self.product_name.replace('-', '_')
                self.source_code=f'{self.source_code_path}/imports_and_integrations'
                self.path_to_dockerfile=f'{self.source_code}/airflow'
                self.dockerfile_name='Dockerfile_airflow'
                self.docker_image_name="iai-cron"
                self.docker_buildargs={}
                self.code_build_command=""
                self.env_vars_chech_enabled=True
                self.deployment_bucket_dir=f'iai_cron'
                self.branch_name_variable_jenkins='IMPORTS_AND_INTEGRATIONS_BRANCH_NAME'
                self.expected_health_check_response_code=response_code
                
                self.list_of_files_to_update_creds=[
                    f'{self.source_code}/airflow/docker/pip.conf'
                ]

                if template_dir == '':
                    self.template_location=f'{self.templates_base_dir}/iai_cron'
                else:
                    self.template_location=f'{self.templates_base_dir}/{template_dir}'
                if template_name == '':
                    self.template_name="iai-cron-dc.yaml.j2"
                else:
                    self.template_name=template_name

                if self.use_local_variables_file:
                    self.default_env_variables='deployments/secrets'
                    self.local_variables_dir=f'{self.source_code}/deployments'
                    if self.level == 'dev':
                        self.local_variables_file=f'variables_{product_name_underscore}_dev'
                        if self.aws_region == 'us-east-1':
                            self.environment_variables_from_secret='dev-us-iai-cron-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.environment_variables_from_secret='dev-eu-iai-cron-secrets'
                    elif self.level == 'stage':
                        self.local_variables_file = f'variables_{product_name_underscore}_stage'
                        if self.aws_region == 'us-east-1':
                            self.environment_variables_from_secret='stage-us-iai-cron-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.environment_variables_from_secret='stage-eu-iai-cron-secrets'
                    elif self.level == 'prod':
                        if self.aws_region == 'us-east-1':
                            self.local_variables_file = f'variables_{product_name_underscore}_prod_us'
                            self.environment_variables_from_secret='prod-us-iai-cron-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.local_variables_file=f'variables_{product_name_underscore}_prod_eu'
                            self.environment_variables_from_secret='prod-eu-iai-cron-secrets'
                else: 
                    self.default_env_variables=f'{self.path_to_dockerfile}/env.example'
                    if self.level == 'dev':
                        self.environment_variables_from_secret=f'local-{self.env}-iai-cron-secrets'
                    else:
                        self.environment_variables_from_secret=f'{self.env}-vars'

                if 'prod-us' in self.env:
                    self.aws_logs_group='iai-cron-prod-us'
                elif 'prod-eu' in self.env:
                    self.aws_logs_group='iai-cron-prod-eu'
                else:
                    self.aws_logs_group='iai-cron-stage'

                if os.path.exists(self.source_code):
                    self.version=f'{self.get_git_branch(self.source_code).replace("/", "_")}_{self.get_git_hash(self.source_code)}'
                else:
                    print_log_message(log_level='ERROR', msg=f'Missing source coede {self.source_code}')
                    sys.exit(1)
                self.tag=f'{self.default_ecr_registry}/{self.docker_image_name}:{self.version}'

                self.docker_build_command=f'''DOCKER_BUILDKIT=1 docker build \
                                                 --secret id=pip_conf,src={self.path_to_dockerfile}/docker/pip.conf \
                                                -t {self.tag} -f {self.dockerfile_name} .  --progress plain --network=host {self.no_cache}'''
            ######################################################################################################################################################        
            case 'sched1-airflow':
                self.product_name='sched1-airflow'
                self.source_code=f'{self.source_code_path}/scheduler'
                self.path_to_dockerfile=f'{self.source_code}'
                self.dockerfile_name='Dockerfile'
                self.docker_image_name=self.product_name
                self.docker_buildargs={}
                self.code_build_command=""
                self.env_vars_chech_enabled=True
                self.deployment_bucket_dir=f'sched1-airflow'
                self.branch_name_variable_jenkins='SCHEDULER_AIRFLOW_SERVICE_BRANCH_NAME'
                self.expected_health_check_response_code=response_code

                self.list_of_files_to_update_creds=[
                    f'{self.source_code}/maven-settings.xml',                    
                    f'{self.source_code}/docker_build_files/sources.list',
                ]

                if template_dir == '':
                    self.template_location=f'{self.templates_base_dir}/sched1-airflow'
                else:
                    self.template_location=f'{self.templates_base_dir}/{template_dir}'
                if template_name == '':
                    self.template_name="sched1-airflow-dc.yaml.j2"
                else:
                    self.template_name=template_name

                if self.use_local_variables_file:
                    self.default_env_variables='deployments/secrets'
                    self.local_variables_dir=f'{self.source_code}/deployments'
                    if self.level == 'dev':
                        self.local_variables_file='variables_dev'
                        if self.aws_region == 'us-east-1':
                            self.environment_variables_from_secret='dev-us-scheduler-airflow-service-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.environment_variables_from_secret='dev-eu-scheduler-airflow-service-secrets'
                    elif self.level == 'stage':
                        self.local_variables_file='variables_stage'
                        if self.aws_region == 'us-east-1':
                            self.environment_variables_from_secret='stage-us-scheduler-airflow-service-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.environment_variables_from_secret='stage-eu-scheduler-airflow-service-secrets'
                    elif self.level == 'prod':
                        if self.aws_region == 'us-east-1':
                            self.local_variables_file='variables_prod_us'
                            self.environment_variables_from_secret='prod-us-scheduler-airflow-service-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.local_variables_file='variables_prod_eu'
                            self.environment_variables_from_secret='prod-eu-scheduler-airflow-service-secrets'
                else: 
                    self.default_env_variables='env.sched.airflow.exmaple'
                    if self.level == 'dev':
                        self.environment_variables_from_secret=f'local-{self.env}-scheduler-airflow-service-secrets'
                    else:
                        self.environment_variables_from_secret=f'{self.env}-vars'

                if 'prod-us' in self.env:
                    self.aws_logs_group='sched1-prod-us'
                elif 'prod-eu' in self.env:
                    self.aws_logs_group='sched1-prod-eu'
                else:
                    self.aws_logs_group='sched1'

                if os.path.exists(self.source_code):
                    self.version=f'{self.get_git_branch(self.source_code).replace("/", "_")}_{self.get_git_hash(self.source_code)}'
                else:
                    print_log_message(log_level='ERROR', msg=f'Missing source coede {self.source_code}')
                    sys.exit(1)
                self.tag=f'{self.default_ecr_registry}/{self.docker_image_name}:{self.version}'
                self.docker_build_command=f'''DOCKER_BUILDKIT=1 docker build \
                                                -t {self.tag} -f {self.dockerfile_name} .  --progress plain --network=host {self.no_cache}'''
            ######################################################################################################################################################
            case 'old-data-etls':
                self.product_name='old-data-etls'
                self.source_code=f'{self.source_code_path}/old_data_etls'
                self.path_to_dockerfile=f'{self.source_code}/Airflow/airflow'
                self.dockerfile_name='Dockerfile'
                self.docker_image_name=self.product_name
                self.docker_buildargs={}
                self.code_build_command=""
                self.env_vars_chech_enabled=True
                self.deployment_bucket_dir=f'old_data_etls'
                self.branch_name_variable_jenkins='ANALYTICS_ETL_BRANCH_NAME'
                self.expected_health_check_response_code=response_code

                self.list_of_files_to_update_creds=[
                    f'{self.source_code}/Airflow/airflow/docker/pip.conf',
                    f'{self.source_code}/Airflow/airflow/docker/sources.list'
                ]

                if template_dir == '':
                    self.template_location=f'{self.templates_base_dir}/old_data_etls'
                else:
                    self.template_location=f'{self.templates_base_dir}/{template_dir}'
                if template_name == '':
                    self.template_name="old-data-etls-dc.yaml.j2"
                else:
                    self.template_name=template_name

                if self.use_local_variables_file:
                    self.default_env_variables='deployments/secrets'
                    self.local_variables_dir=f'{self.source_code}/deployments'
                    if self.level == 'dev':
                        self.local_variables_file='variables_dev'
                        if self.aws_region == 'us-east-1':
                            self.environment_variables_from_secret='dev-us-old-data-etls-service-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.environment_variables_from_secret='dev-eu-old-data-etls-service-secrets'
                    elif self.level == 'stage':
                        self.local_variables_file='variables_stage'
                        if self.aws_region == 'us-east-1':
                            self.environment_variables_from_secret='stage-us-old-data-etls-service-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.environment_variables_from_secret='stage-eu-old-data-etls-service-secrets'
                    elif self.level == 'prod':
                        if self.aws_region == 'us-east-1':
                            self.local_variables_file='variables_prod_us'
                            self.environment_variables_from_secret='prod-us-old-data-etls-service-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.local_variables_file='variables_prod_eu'
                            self.environment_variables_from_secret='prod-eu-old-data-etls-service-secrets'
                else: 
                    self.default_env_variables='env.exmaple'
                    if self.level == 'dev':
                        self.environment_variables_from_secret=f''
                    else:
                        self.environment_variables_from_secret=f''

                if 'prod-us' in self.env:
                    self.aws_logs_group='old-data-etls-prod-us'
                elif 'prod-eu' in self.env:
                    self.aws_logs_group='old-data-etls-prod-eu'
                else:
                    self.aws_logs_group='old-data-etls'

                if os.path.exists(self.source_code):
                    self.version=f'{self.get_git_branch(self.source_code).replace("/", "_")}_{self.get_git_hash(self.source_code)}'
                else:
                    print_log_message(log_level='ERROR', msg=f'Missing source coede {self.source_code}')
                    sys.exit(1)
                self.tag=f'{self.default_ecr_registry}/{self.docker_image_name}:{self.version}'

                self.copy_files_tree(f'{self.source_code}/Airflow/dbupdown', f'{self.path_to_dockerfile}/docker/dbupdown')
                self.copy_files_tree(f'{self.source_code}/Airflow/tools', f'{self.path_to_dockerfile}/docker/tools')
                shutil.copy2(f'{self.source_code}/requirements.txt', f'{self.path_to_dockerfile}/docker/requirements.txt')

                self.docker_build_command=f'''DOCKER_BUILDKIT=1 docker build \
		                                                                --secret id=pip_conf,src={self.path_to_dockerfile}/docker/pip.conf \
		                                                                -t {self.tag} -f {self.dockerfile_name} .  --progress plain --network=host {self.no_cache}'''
            ######################################################################################################################################################
            case 'api-gateway-service':
                self.product_name='api-gateway-service'
                self.source_code=f'{self.source_code_path}/api-gateway-service'
                self.path_to_dockerfile=f'{self.source_code}'
                self.dockerfile_name='Dockerfile'
                self.docker_image_name="api-gateway-service"
                self.docker_buildargs={}
                self.code_build_command=""
                self.env_vars_chech_enabled=True
                self.deployment_bucket_dir=f'api_gateway/'
                self.branch_name_variable_jenkins='API_GATEWAY_SERVICE_BRANCH_NAME'
                self.expected_health_check_response_code=response_code
                
                self.list_of_files_to_update_creds=[]

                
                if template_dir == '':
                    self.template_location=f'{self.templates_base_dir}/gateway_service'
                else:
                    self.template_location=f'{self.templates_base_dir}/{template_dir}'
                if template_name == '':
                    self.template_name="api-gateway-service-dc-localvars.yml.j2"
                else:
                    self.template_name=template_name

                if self.use_local_variables_file:
                    self.default_env_variables='deployments/secrets'
                    self.local_variables_dir=f'{self.source_code}/deployments'
                    if self.level == 'dev':
                        self.local_variables_file='variables_dev'
                        if self.aws_region == 'us-east-1':
                            self.environment_variables_from_secret='dev-us-api-gateway-service-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.environment_variables_from_secret='dev-eu-api-gateway-service-secrets'
                    elif self.level == 'stage':
                        self.local_variables_file='variables_stage'
                        if self.aws_region == 'us-east-1':
                            self.environment_variables_from_secret='stage-us-api-gateway-service-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.environment_variables_from_secret='stage-eu-api-gateway-service-secrets'
                    elif self.level == 'prod':
                        if self.aws_region == 'us-east-1':
                            self.local_variables_file='variables_prod_us'
                            self.environment_variables_from_secret='prod-us-api-gateway-service-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.local_variables_file='variables_prod_eu'
                            self.environment_variables_from_secret='prod-eu-api-gateway-service-secrets'
                else: 
                    self.default_env_variables='env.example'
                    if self.level == 'dev':
                        self.environment_variables_from_secret=f'local-{self.env}-api-gateway-service-secrets'
                    else:
                        self.environment_variables_from_secret=f'{self.env}-vars'

                if 'prod-us' in self.env:
                    self.aws_logs_group='java-prod-us'
                elif 'prod-eu' in self.env:
                    self.aws_logs_group='java-prod-eu'
                else:
                    self.aws_logs_group='java_instances_stage'

                if os.path.exists(self.source_code):
                    self.version=f'{self.get_git_branch(self.source_code).replace("/", "_")}_{self.get_git_hash(self.source_code)}'
                else:
                    print_log_message(log_level='ERROR', msg=f'Missing source coede {self.source_code}')
                    sys.exit(1)
                self.tag=f'{self.default_ecr_registry}/{self.docker_image_name}:{self.version}'

                self.docker_build_command=f'''DOCKER_BUILDKIT=1 docker build \
                                                --build-arg USB_USER={self.user} \
                                                --build-arg USB_PASS={self.password} \
                                                --build-arg USB_PROXY_URL={self.proxy} \
                                                -t {self.tag} -f {self.dockerfile_name} .  --progress plain --network=host'''
            ######################################################################################################################################################
            case 'qr-code-service':
                self.product_name='qr-code-service'
                self.source_code=f'{self.source_code_path}/qr-code-service'
                self.path_to_dockerfile=f'{self.source_code}'
                self.dockerfile_name='Dockerfile'
                self.docker_image_name="qr-code-service"
                self.docker_buildargs={}
                self.code_build_command=""
                self.env_vars_chech_enabled=True
                self.deployment_bucket_dir=f'qr_code_service/'
                self.branch_name_variable_jenkins='QR_CODE_SERVICE_BRANCH_NAME'
                self.expected_health_check_response_code=response_code
                
                self.list_of_files_to_update_creds=[]

                
                if template_dir == '':
                    self.template_location=f'{self.templates_base_dir}/qr_code_service'
                else:
                    self.template_location=f'{self.templates_base_dir}/{template_dir}'
                if template_name == '':
                    self.template_name="qr-code-service-dc-localvars.yml.j2"
                else:
                    self.template_name=template_name

                if self.use_local_variables_file:
                    self.default_env_variables='deployments/secrets'
                    self.local_variables_dir=f'{self.source_code}/deployments'
                    if self.level == 'dev':
                        self.local_variables_file='variables_dev'
                        if self.aws_region == 'us-east-1':
                            self.environment_variables_from_secret='dev-us-qr-code-service-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.environment_variables_from_secret='dev-eu-qr-code-service-secrets'
                    elif self.level == 'stage':
                        self.local_variables_file='variables_stage'
                        if self.aws_region == 'us-east-1':
                            self.environment_variables_from_secret='stage-us-qr-code-service-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.environment_variables_from_secret='stage-eu-qr-code-service-secrets'
                    elif self.level == 'prod':
                        if self.aws_region == 'us-east-1':
                            self.local_variables_file='variables_prod_us'
                            self.environment_variables_from_secret='prod-us-qr-code-service-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.local_variables_file='variables_prod_eu'
                            self.environment_variables_from_secret='prod-eu-qr-code-service-secrets'
                else: 
                    self.default_env_variables='env.example'
                    if self.level == 'dev':
                        self.environment_variables_from_secret=f'local-{self.env}-qr-code-service-secrets'
                    else:
                        self.environment_variables_from_secret=f'{self.env}-vars'

                if 'prod-us' in self.env:
                    self.aws_logs_group='java-prod-us'
                elif 'prod-eu' in self.env:
                    self.aws_logs_group='java-prod-eu'
                else:
                    self.aws_logs_group='java_instances_stage'

                if os.path.exists(self.source_code):
                    self.version=f'{self.get_git_branch(self.source_code).replace("/", "_")}_{self.get_git_hash(self.source_code)}'
                else:
                    print_log_message(log_level='ERROR', msg=f'Missing source coede {self.source_code}')
                    sys.exit(1)
                self.tag=f'{self.default_ecr_registry}/{self.docker_image_name}:{self.version}'

                self.docker_build_command=f'''DOCKER_BUILDKIT=1 docker build \
                                                --build-arg USB_USER={self.user} \
                                                --build-arg USB_PASS={self.password} \
                                                --build-arg USB_PROXY_URL={self.proxy} \
                                                -t {self.tag} -f {self.dockerfile_name} .  --progress plain --network=host'''
            ######################################################################################################################################################
            case 'torch-api':
                self.product_name='torch-api'
                self.source_code=f'{self.source_code_path}/torch-api'
                self.path_to_dockerfile=f'{self.source_code}'
                self.dockerfile_name='Dockerfile'
                self.docker_image_name="torch-api"
                self.docker_buildargs={}
                self.code_build_command=""
                self.env_vars_chech_enabled=True
                self.deployment_bucket_dir=f'torch_api/'
                self.branch_name_variable_jenkins='TORCH_API_BRANCH_NAME'
                self.expected_health_check_response_code=response_code
                
                self.list_of_files_to_update_creds=[]

                
                if template_dir == '':
                    self.template_location=f'{self.templates_base_dir}/torch-api'
                else:
                    self.template_location=f'{self.templates_base_dir}/{template_dir}'
                if template_name == '':
                    self.template_name="torch-api-dc-localvars.yml.j2"
                else:
                    self.template_name=template_name

                if self.use_local_variables_file:
                    self.default_env_variables='deployments/secrets'
                    self.local_variables_dir=f'{self.source_code}/deployments'
                    if self.level == 'dev':
                        self.local_variables_file='variables_dev'
                        if self.aws_region == 'us-east-1':
                            self.environment_variables_from_secret='dev-us-torch-api-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.environment_variables_from_secret='dev-eu-torch-api-secrets'
                    elif self.level == 'stage':
                        self.local_variables_file='variables_stage'
                        if self.aws_region == 'us-east-1':
                            self.environment_variables_from_secret='stage-us-torch-api-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.environment_variables_from_secret='stage-eu-torch-api-secrets'
                    elif self.level == 'prod':
                        if self.aws_region == 'us-east-1':
                            self.local_variables_file='variables_prod_us'
                            self.environment_variables_from_secret='prod-us-torch-api-secrets'
                        elif self.aws_region == 'eu-west-1':
                            self.local_variables_file='variables_prod_eu'
                            self.environment_variables_from_secret='prod-eu-torch-api-secrets'
                else: 
                    self.default_env_variables='env.example'
                    if self.level == 'dev':
                        self.environment_variables_from_secret=f'local-{self.env}-torch-api-secrets'
                    else:
                        self.environment_variables_from_secret=f'{self.env}-vars'

                if 'prod-us' in self.env:
                    self.aws_logs_group='java-prod-us'
                elif 'prod-eu' in self.env:
                    self.aws_logs_group='java-prod-eu'
                else:
                    self.aws_logs_group='java_instances_stage'

                if os.path.exists(self.source_code):
                    self.version=f'{self.get_git_branch(self.source_code).replace("/", "_")}_{self.get_git_hash(self.source_code)}'
                else:
                    print_log_message(log_level='ERROR', msg=f'Missing source coede {self.source_code}')
                    sys.exit(1)
                self.tag=f'{self.default_ecr_registry}/{self.docker_image_name}:{self.version}'

                self.docker_build_command=f'''DOCKER_BUILDKIT=1 docker build \
                                                --build-arg USB_USER={self.user} \
                                                --build-arg USB_PASS={self.password} \
                                                --build-arg USB_PROXY_URL={self.proxy} \
                                                -t {self.tag} -f {self.dockerfile_name} .  --progress plain --network=host'''
                                            
######################################################################################################################################################
        # Variables for local environment variables file
        self.local_variables_file_fill_values = {
            'dev-us': {
                'db_host': 'db-talech',
                'pos_db_host': 'db-talech',
                'pos_db_replica_1': 'db-talech',
                'pos_db_archive': 'db-talech',
                'pos_db': 'pos_local',
                'intsrv_db_host': 'db-talech',
                'intsrv_db': 'intsrv',
                'scheduler_db_host': 'db-talech',
                'scheduler_db': 'scheduler_local',
                'oauth_db_host': 'db-talech',
                'oauth_db': 'oauth',
                'web_db_host': 'db-talech',
                'web_db': 'website',
                'old_cron_db_host': 'cron-db',
                'old_cron_db': 'airflow',
                'web_cron_db_host': 'cron-db',
                'web_cron_db': 'airflow',
                'metrix_airflow_db_host': 'metrix-airflow-db',
                'metrix_airflow_db': 'airflow',
                'iai_cron_db_host': 'iai-cron-db',
                'iai_cron_db': 'airflow-iai-cron',
                'iai_cron_feature_db_host': 'iai-cron-feature-db',
                'iai_cron_feature_db': 'airflow',
                'scheduler_airflow_db_host': 'sched1-airflow',
                'scheduler_airflow_db_name': 'db-sched1-airflow',
                'druid_db_host': 'postgres',
                'druid_db': 'druid',
                'payroll_db_host': 'payroll-postgres',
                'payroll_db': 'payroll_postgres',
                'web_redis_host': 'web-redis',
                'iai_redis_host': 'iai-redis',
                'druid_broker_host': 'brokerd',
                'druid_router_host': 'router',
                'druid_middlemanager_host': 'middlemanager',
                'druid_historical_host': 'historical',
                'druid_coordinator_host': 'coordinator',
                'druid_storage_bucket': '',
                'zookeeper_host': 'zookeeper',
                'emr_cluster': '',
                'env_with_region': f'dev-us-{self.env[4:]}',
                'env_level_with_region': 'dev-us',
                'queue_prefix': self.env,
                'appd_name': '4801-DEV',
                'legacy_sqs_naming': '',
                'cdn_url': 'https://dev-cdn-us.talech.com',
            },
            'dev-eu': {
                'db_host': 'db-talech',
                'pos_db_host': 'db-talech',
                'pos_db_replica_1': 'db-talech',
                'pos_db_archive': 'db-talech',
                'pos_db': 'pos_local',
                'intsrv_db_host': 'db-talech',
                'intsrv_db': 'intsrv',
                'scheduler_db_host': 'db-talech',
                'scheduler_db': 'scheduler_local',
                'oauth_db_host': 'db-talech',
                'oauth_db': 'oauth',
                'web_db_host': 'db-talech',
                'web_db': 'website',
                'old_cron_db_host': 'cron-db',
                'old_cron_db': 'airflow',
                'web_cron_db_host': 'cron-db',
                'web_cron_db': 'airflow',
                'metrix_airflow_db_host': 'metrix-airflow-db',
                'metrix_airflow_db': 'airflow',
                'iai_cron_db_host': 'iai-cron-db',
                'iai_cron_db': 'airflow-iai-cron',
                'iai_cron_feature_db_host': 'iai-cron-feature-db',
                'iai_cron_feature_db': 'airflow',
                'druid_db_host': 'postgres',
                'druid_db': 'druid',
                'payroll_db_host': 'payroll-postgres',
                'payroll_db': 'payroll_postgres',
                'web_redis_host': 'web-redis',
                'iai_redis_host': 'iai-redis',
                'scheduler_airflow_db_host': 'sched1-airflow',
                'scheduler_airflow_db_name': 'db-sched1-airflow',
                'druid_broker_host': 'brokerd',
                'druid_router_host': 'router',
                'druid_middlemanager_host': 'middlemanager',
                'druid_historical_host': 'historical',
                'druid_coordinator_host': 'coordinator',
                'druid_storage_bucket': '',
                'zookeeper_host': 'zookeeper',
                'emr_cluster': '',
                'env_with_region': self.env,
                'env_level_with_region': 'dev-eu',
                'queue_prefix': self.env,
                'appd_name': '8363-DEV',
                'legacy_sqs_naming': '',
                'cdn_url': 'https://dev-cdn-eu.talech.com',
            },
            'ops-1': {
                'db_host': 'ops-01-v5-7.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'pos_db_host': 'ops-01-v5-7.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'pos_db_replica_1': 'ops-01-v5-7.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'pos_db_archive': 'ops-01-v5-7.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'pos_db': 'pos2',
                'intsrv_db_host': 'ops-01-v5-7.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'intsrv_db': 'intsrv',
                'scheduler_db_host': 'ops-01-v5-7.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'scheduler_db': 'schedulerDS',
                'oauth_db_host': 'ops-01-v5-7.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'oauth_db': 'oauth',
                'web_db_host': 'ops-01-v5-7.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'web_db': 'website2',
                'old_cron_db_host': 'web-cron-ops-1-db.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'old_cron_db': 'airflow',
                'web_cron_db_host': 'web-cron-nextgen-ops-1-db.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'web_cron_db': 'airflow',
                'metrix_airflow_db_host': 'metrix-airflow-ops-1-db.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'metrix_airflow_db': 'airflow',
                'iai_cron_db_host': 'iai-cron-ops-1-db.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'iai_cron_db': 'iai_cron_ops_1_db',
                'iai_cron_feature_db_host': 'iai-cron-feature-ops-1-db.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'iai_cron_feature_db': 'iai_cron_feature_ops_1_db',
                'scheduler_airflow_db_host': 'sched1-airflow',
                'scheduler_airflow_db_name': 'db-sched1-airflow',
                'druid_db_host': 'druid-postgress-ops-1-db.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'druid_db': 'druid',
                'payroll_db_host': 'iai-cron-feature-ops-1-db.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'payroll_db': 'payroll_postgres',
                'web_redis_host': 'elasticache-ops-1.fptd2x.clustercfg.use1.cache.amazonaws.com',
                'iai_redis_host': 'iai-redis',
                'druid_broker_host': 'druid-query-ops-1-nlb-0b5123bddac2e5cd.elb.us-east-1.amazonaws.com',
                'druid_router_host': 'router',
                'druid_middlemanager_host': 'middlemanager',
                'druid_historical_host': 'historical',
                'druid_coordinator_host': 'druid-master-ops-1-nlb-1bad9c791964b95a.elb.us-east-1.amazonaws.com',
                'druid_storage_bucket': 'talech-ops-1-emr-us-east-1',
                'zookeeper_host': 'druid-master-ops-1-nlb-1bad9c791964b95a.elb.us-east-1.amazonaws.com',
                'emr_cluster': 'j-K5NJC7VD35VU',
                'env_with_region': 'ops-us-1',
                'env_level_with_region': 'stage-us',
                'queue_prefix': 'ops-1',
                'appd_name': '4801-OPS-1',
                'legacy_sqs_naming': '',
                'cdn_url': 'https://stage-cdn-us.talech.com',
            },
            'qa-1': {
                'db_host': 'vpc-posinstance-5-6-m-qa.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'pos_db_host': 'vpc-posinstance-5-6-m-qa.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'pos_db_replica_1': 'vpc-posinstance-5-6-m-qa.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'pos_db_archive': 'vpc-posinstance-5-6-m-qa.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'pos_db': 'pos2',
                'intsrv_db_host': 'vpc-posinstance-5-6-m-qa.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'intsrv_db': 'intsrv',
                'scheduler_db_host': 'vpc-posinstance-5-6-m-qa.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'scheduler_db': 'schedulerDS',
                'oauth_db_host': 'vpc-posinstance-5-6-m-qa.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'oauth_db': 'oauth',
                'web_db_host': 'vpc-posinstance-5-6-m-qa.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'web_db': 'website2',
                'old_cron_db_host': 'web-cron-qa-1-db.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'old_cron_db': 'airflow2',
                'web_cron_db_host': 'web-cron-nextgen-qa-1-db.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'web_cron_db': 'airflow',
                'metrix_airflow_db_host': 'metrix-airflow-qa-1-db.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'metrix_airflow_db': 'airflow',
                'iai_cron_db_host': 'iai-cron-qa-1-db.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'iai_cron_db': 'airflow-iai-cron',
                'iai_cron_feature_db_host': 'iai-cron-feature-db',
                'iai_cron_feature_db': 'airflow',
                'scheduler_airflow_db_host': 'sched1-airflow',
                'scheduler_airflow_db_name': 'db-sched1-airflow',
                'druid_db_host': 'druid-postgress-qa-1-db.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'druid_db': 'druid',
                'payroll_db_host': 'payroll-postgres',
                'payroll_db': 'payroll_postgres',
                'web_redis_host': 'elasticache-qa-1.fptd2x.clustercfg.use1.cache.amazonaws.com',
                'iai_redis_host': 'iai-redis',
                'druid_broker_host': 'druid-query-qa-1-nlb-920583b43b5e1b8d.elb.us-east-1.amazonaws.com',
                'druid_router_host': 'router',
                'druid_middlemanager_host': 'middlemanager',
                'druid_historical_host': 'historical',
                'druid_coordinator_host': 'coordinator',
                'druid_storage_bucket': 'talech-qa-1-emr-us-east-1',
                'zookeeper_host': 'druid-master-qa-1-nlb-a2526ece477e833e.elb.us-east-1.amazonaws.com',
                'emr_cluster': 'j-1LXGUYMQH8JPE',
                'env_with_region': 'qa-us-1',
                'env_level_with_region': 'stage-us',
                'queue_prefix': 'qa-1',
                'appd_name': '4801-QA-1',
                'legacy_sqs_naming': '',
                'cdn_url': 'https://stage-cdn-us.talech.com',
            }, 
            'qa-2': {
                'db_host': 'vpc-posinstance-5-6-m-qa-2.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'pos_db_host': 'vpc-posinstance-5-6-m-qa-2.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'pos_db_replica_1': 'vpc-posinstance-5-6-m-qa-2.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'pos_db_archive': 'vpc-posinstance-5-6-m-qa-2.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'pos_db': 'pos2',
                'intsrv_db_host': 'vpc-posinstance-5-6-m-qa-2.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'intsrv_db': 'intsrv',
                'scheduler_db_host': 'vpc-posinstance-5-6-m-qa-2.cbj6fnelphl2.us-east-1.rds.amazonaws.comh',
                'scheduler_db': 'schedulerDS',
                'oauth_db_host': 'vpc-posinstance-5-6-m-qa-2.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'oauth_db': 'oauth',
                'web_db_host': 'vpc-posinstance-5-6-m-qa-2.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'web_db': 'website2',
                'old_cron_db_host': 'web-cron-qa-2-db.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'old_cron_db': 'airflow2',
                'web_cron_db_host': 'web-cron-nextgen-qa-2-db.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'web_cron_db': 'airflow',
                'metrix_airflow_db_host': 'metrix-airflow-qa-2-db.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'metrix_airflow_db': 'airflow',
                'iai_cron_db_host': 'iai-cron-qa-2-db.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'iai_cron_db': 'airflow-iai-cron',
                'iai_cron_feature_db_host': 'iai-cron-feature-db',
                'iai_cron_feature_db': 'airflow',
                'scheduler_airflow_db_host': 'sched1-airflow',
                'scheduler_airflow_db_name': 'db-sched1-airflow',
                'druid_db_host': 'druid-postgress-qa-2-db.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'druid_db': 'druid',
                'payroll_db_host': 'payroll-postgres',
                'payroll_db': 'payroll_postgres',
                'web_redis_host': 'elasticache-qa-2.fptd2x.clustercfg.use1.cache.amazonaws.com',
                'iai_redis_host': 'iai-redis',
                'druid_broker_host': 'druid-query-qa-2-nlb-0810fcb397b46191.elb.us-east-1.amazonaws.com',
                'druid_router_host': 'router',
                'druid_middlemanager_host': 'middlemanager',
                'druid_historical_host': 'historical',
                'druid_coordinator_host': 'druid-master-qa-2-nlb-35c6cba03e25e6c3.elb.us-east-1.amazonaws.com',
                'druid_storage_bucket': 'talech-qa-2-emr-us-east-1',
                'zookeeper_host': 'druid-master-qa-2-nlb-35c6cba03e25e6c3.elb.us-east-1.amazonaws.com',
                'emr_cluster': 'j-1LXGUYMQH8JPE',
                'env_with_region': 'qa-us-2',
                'env_level_with_region': 'stage-us',
                'queue_prefix': 'qa-2',
                'appd_name': '4801-QA-2',
                'legacy_sqs_naming': '',
                'cdn_url': 'https://stage-cdn-us.talech.com',
            },
            'stage-1': {
                'db_host': 'stage-01-v5-7.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'pos_db_host': 'stage-01-v5-7.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'pos_db_replica_1': 'stage-01-v5-7.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'pos_db_archive': 'stage-01-v5-7.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'pos_db': 'pos2',
                'intsrv_db_host': 'stage-01-v5-7.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'intsrv_db': 'intsrv',
                'scheduler_db_host': 'stage-01-v5-7.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'scheduler_db': 'schedulerDS',
                'oauth_db_host': 'stage-01-v5-7.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'oauth_db': 'oauth',
                'web_db_host': 'stage-01-v5-7.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'web_db': 'website2',
                'old_cron_db_host': 'web-cron-stage-1-db.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'old_cron_db': 'airflow2',
                'web_cron_db_host': 'web-cron-nextgen-stage-1-db.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'web_cron_db': 'airflow',
                'metrix_airflow_db_host': 'metrix-airflow-stage-1-db.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'metrix_airflow_db': 'airflow',
                'scheduler_airflow_db_host': 'sched1-airflow',
                'scheduler_airflow_db_name': 'db-sched1-airflow',
                'iai_cron_db_host': 'iai-cron-stage-1-db.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'iai_cron_db': 'airflow-iai-cron',
                'iai_cron_feature_db_host': 'iai-cron-feature-db',
                'iai_cron_feature_db': 'airflow',
                'druid_db_host': 'druid-postgress-stage-1-db.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'druid_db': 'druid',
                'payroll_db_host': 'payroll-postgres',
                'payroll_db': 'payroll_postgres',
                'web_redis_host': 'elasticache-stage-1.fptd2x.clustercfg.use1.cache.amazonaws.com',
                'iai_redis_host': 'iai-redis',
                'druid_broker_host': 'druid-query-stage-1-nlb-08509032fc1b5c32.elb.us-east-1.amazonaws.com',
                'druid_router_host': 'router',
                'druid_middlemanager_host': 'middlemanager',
                'druid_historical_host': 'historical',
                'druid_coordinator_host': 'druid-master-stage-1-nlb-f0b995694de2ac66.elb.us-east-1.amazonaws.com',
                'druid_storage_bucket': 'talech-stage-1-emr-us-east-1',
                'zookeeper_host': 'druid-master-stage-1-nlb-f0b995694de2ac66.elb.us-east-1.amazonaws.com',
                'emr_cluster': 'j-K5NJC7VD35VU',
                'env_with_region': 'stage-us-1',
                'env_level_with_region': 'stage-us',
                'queue_prefix': 'stage-1',
                'appd_name': '4801-STAGE-1',
                'legacy_sqs_naming': 'stage',
                'cdn_url': 'https://stage-cdn-us.talech.com',
            },
            'stage-2': {
                'db_host': 'stage-02-v5-7.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'pos_db_host': 'stage-02-v5-7.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'pos_db_replica_1': 'stage-02-v5-7.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'pos_db_archive': 'stage-02-v5-7.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'pos_db': 'pos2',
                'intsrv_db_host': 'stage-02-v5-7.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'intsrv_db': 'intsrv',
                'scheduler_db_host': 'stage-02-v5-7.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'scheduler_db': 'schedulerDS',
                'oauth_db_host': 'stage-02-v5-7.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'oauth_db': 'oauth',
                'web_db_host': 'stage-02-v5-7.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'web_db': 'website2',
                'old_cron_db_host': 'web-cron-stage-2-db.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'old_cron_db': 'airflow2',
                'web_cron_db_host': 'web-cron-nextgen-stage-2-db.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'web_cron_db': 'airflow',
                'metrix_airflow_db_host': 'metrix-airflow-stage-2-db.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'metrix_airflow_db': 'airflow',
                'iai_cron_db_host': 'iai-cron-stage-2-db.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'iai_cron_db': 'airflow-iai-cron',
                'iai_cron_feature_db_host': 'iai-cron-feature-db',
                'iai_cron_feature_db': 'airflow',
                'scheduler_airflow_db_host': 'sched1-airflow',
                'scheduler_airflow_db_name': 'db-sched1-airflow',
                'druid_db_host': 'druid-postgress-stage-2-db.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'druid_db': 'druid',
                'payroll_db_host': 'payroll-postgres',
                'payroll_db': 'payroll_postgres',
                'web_redis_host': 'elasticache-stage-2.fptd2x.clustercfg.use1.cache.amazonaws.com',
                'iai_redis_host': 'iai-redis',
                'druid_broker_host': 'druid-query-stage-2-nlb-0b5123bddac2e5cd.elb.us-east-1.amazonaws.com',
                'druid_router_host': 'router',
                'druid_middlemanager_host': 'middlemanager',
                'druid_historical_host': 'historical',
                'druid_coordinator_host': 'druid-master-stage-2-nlb-1bad9c791964b95a.elb.us-east-1.amazonaws.com',
                'druid_storage_bucket': 'talech-stage-2-emr-us-east-1',
                'zookeeper_host': 'druid-master-stage-2-nlb-1bad9c791964b95a.elb.us-east-1.amazonaws.com',
                'emr_cluster': 'j-K5NJC7VD35VU',
                'env_with_region': 'stage-us-2',
                'env_level_with_region': 'stage-us',
                'queue_prefix': 'stage-2',
                'appd_name': '4801-STAGE-2',
                'legacy_sqs_naming': '',
                'cdn_url': 'https://stage-cdn-us.talech.com',
            },
            'stage-3': {
                'db_host': 'stage-03-v5-7.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'pos_db_host': 'stage-03-v5-7.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'pos_db_replica_1': 'stage-03-v5-7.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'pos_db_archive': 'stage-03-v5-7.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'pos_db': 'pos2',
                'intsrv_db_host': 'stage-03-v5-7.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'intsrv_db': 'intsrv',
                'scheduler_db_host': 'stage-03-v5-7.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'scheduler_db': 'schedulerDS',
                'oauth_db_host': 'stage-03-v5-7.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'oauth_db': 'oauth',
                'web_db_host': 'stage-03-v5-7.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'web_db': 'website2',
                'old_cron_db_host': 'web-cron-stage-3-db.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'old_cron_db': 'airflow2',
                'web_cron_db_host': 'web-cron-nextgen-stage-3-db.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'web_cron_db': 'airflow',
                'metrix_airflow_db_host': 'metrix-airflow-stage-3-db.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'metrix_airflow_db': 'airflow',
                'iai_cron_db_host': 'iai-cron-stage-3-db.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'iai_cron_db': 'airflow-iai-cron',
                'iai_cron_feature_db_host': 'iai-cron-feature-db',
                'iai_cron_feature_db': 'airflow',
                'scheduler_airflow_db_host': 'sched1-airflow',
                'scheduler_airflow_db_name': 'db-sched1-airflow',
                'druid_db_host': 'druid-postgress-stage-3-db.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'druid_db': 'druid',
                'payroll_db_host': 'payroll-postgres',
                'payroll_db': 'payroll_postgres',
                'web_redis_host': 'elasticache-stage-3.fptd2x.clustercfg.use1.cache.amazonaws.com',
                'iai_redis_host': 'iai-redis',
                'druid_broker_host': 'druid-query-stage-3-nlb-6b37f9df475cefae.elb.us-east-1.amazonaws.com',
                'druid_router_host': 'router',
                'druid_middlemanager_host': 'middlemanager',
                'druid_historical_host': 'historical',
                'druid_coordinator_host': 'druid-master-stage-3-nlb-2cfc139f7f3d4f14.elb.us-east-1.amazonaws.com',
                'druid_storage_bucket': 'talech-stage-3-emr-us-east-1',
                'zookeeper_host': 'druid-master-stage-3-nlb-2cfc139f7f3d4f14.elb.us-east-1.amazonaws.com',
                'emr_cluster': 'j-K5NJC7VD35VU',
                'env_with_region': 'stage-us-3',
                'env_level_with_region': 'stage-us',
                'queue_prefix': 'stage-3',
                'appd_name': '4801-STAGE-3',
                'legacy_sqs_naming': '',
                'cdn_url': 'https://stage-cdn-us.talech.com',
            },
            'stage-4': {
                'db_host': 'stage-04-v5-7.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'pos_db_host': 'stage-04-v5-7.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'pos_db_replica_1': 'stage-04-v5-7.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'pos_db_archive': 'stage-04-v5-7.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'pos_db': 'pos2',
                'intsrv_db_host': 'stage-04-v5-7.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'intsrv_db': 'intsrv',
                'scheduler_db_host': 'stage-04-v5-7.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'scheduler_db': 'schedulerDS',
                'oauth_db_host': 'stage-04-v5-7.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'oauth_db': 'oauth',
                'web_db_host': 'stage-04-v5-7.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'web_db': 'website2',
                'old_cron_db_host': 'web-cron-stage-4-db.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'old_cron_db': 'airflow2',
                'web_cron_db_host': 'web-cron-nextgen-stage-4-db.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'web_cron_db': 'airflow',
                'metrix_airflow_db_host': 'metrix-airflow-stage-4-db.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'metrix_airflow_db': 'airflow',
                'iai_cron_db_host': 'iai-cron-stage-4-db.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'iai_cron_db': 'airflow-iai-cron',
                'iai_cron_feature_db_host': 'iai-cron-feature-db',
                'iai_cron_feature_db': 'airflow',
                'scheduler_airflow_db_host': 'sched1-airflow',
                'scheduler_airflow_db_name': 'db-sched1-airflow',
                'druid_db_host': 'druid-postgress-stage-4-db.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'druid_db': 'druid',
                'payroll_db_host': 'payroll-postgres',
                'payroll_db': 'payroll_postgres',
                'web_redis_host': 'elasticache-stage-4.fptd2x.clustercfg.use1.cache.amazonaws.com',
                'iai_redis_host': 'iai-redis',
                'druid_broker_host': 'druid-query-stage-4-nlb-d0d9f6eca3989c02.elb.us-east-1.amazonaws.com',
                'druid_router_host': 'router',
                'druid_middlemanager_host': 'middlemanager',
                'druid_historical_host': 'historical',
                'druid_coordinator_host': 'druid-master-stage-4-nlb-c3de0b126862fb4a.elb.us-east-1.amazonaws.com',
                'druid_storage_bucket': 'talech-stage-4-emr-us-east-1',
                'zookeeper_host': 'druid-master-stage-4-nlb-c3de0b126862fb4a.elb.us-east-1.amazonaws.com',
                'emr_cluster': 'j-1GN53ARTWK3WB',
                'env_with_region': 'stage-us-4',
                'env_level_with_region': 'stage-us',
                'queue_prefix': 'stage-4',
                'appd_name': '4801-STAGE-4',
                'legacy_sqs_naming': '',
                'cdn_url': 'https://stage-cdn-us.talech.com',
            },
            'stage-eu-1': {
                'db_host': 'stage-eu-01-v5-7.coezy0txbb3s.eu-west-1.rds.amazonaws.com',
                'pos_db_host': 'stage-eu-01-v5-7.coezy0txbb3s.eu-west-1.rds.amazonaws.com',
                'pos_db_replica_1': 'stage-eu-01-v5-7.coezy0txbb3s.eu-west-1.rds.amazonaws.com',
                'pos_db_archive': 'stage-eu-01-v5-7.coezy0txbb3s.eu-west-1.rds.amazonaws.com',
                'pos_db': 'pos2',
                'intsrv_db_host': 'stage-eu-01-v5-7.coezy0txbb3s.eu-west-1.rds.amazonaws.com',
                'intsrv_db': 'intsrv',
                'scheduler_db_host': 'stage-eu-01-v5-7.coezy0txbb3s.eu-west-1.rds.amazonaws.com',
                'scheduler_db': 'schedulerDS',
                'oauth_db_host': 'stage-eu-01-v5-7.coezy0txbb3s.eu-west-1.rds.amazonaws.com',
                'oauth_db': 'oauth',
                'web_db_host': 'stage-eu-01-v5-7.coezy0txbb3s.eu-west-1.rds.amazonaws.com',
                'web_db': 'website2',
                'old_cron_db_host': 'web-cron-stage-eu-1-db.coezy0txbb3s.eu-west-1.rds.amazonaws.com',
                'old_cron_db': 'airflow2',
                'web_cron_db_host': 'web-cron-nextgen-stage-eu-1-db.coezy0txbb3s.eu-west-1.rds.amazonaws.com',
                'web_cron_db': 'airflow',
                'metrix_airflow_db_host': 'metrix-airflow-stage-eu-1-db.coezy0txbb3s.eu-west-1.rds.amazonaws.com',
                'metrix_airflow_db': 'airflow',
                'iai_cron_db_host': 'iai-cron-db',
                'iai_cron_db': 'airflow-iai-cron',
                'iai_cron_feature_db_host': 'iai-cron-feature-db',
                'iai_cron_feature_db': 'airflow',
                'scheduler_airflow_db_host': 'sched1-airflow',
                'scheduler_airflow_db_name': 'db-sched1-airflow',
                'druid_db_host': 'druid-postgress-stage-eu-1-db.coezy0txbb3s.eu-west-1.rds.amazonaws.com',
                'druid_db': 'druid',
                'payroll_db_host': 'payroll-postgres',
                'payroll_db': 'payroll_postgres',
                'web_redis_host': 'elasticache-stage-eu-1.o0iblk.clustercfg.euw1.cache.amazonaws.com',
                'iai_redis_host': 'iai-redis',
                'druid_broker_host': 'druid-query-stage-eu-1-nlb-7ccc05fe8c29b369.elb.eu-west-1.amazonaws.com',
                'druid_router_host': 'router',
                'druid_middlemanager_host': 'middlemanager',
                'druid_historical_host': 'historical',
                'druid_coordinator_host': 'druid-master-stage-eu-1-nlb-cb06e4dfdd1b1168.elb.eu-west-1.amazonaws.com',
                'druid_storage_bucket': 'talech-stage-eu-1-emr-eu-west-1',
                'zookeeper_host': 'druid-master-stage-eu-1-nlb-cb06e4dfdd1b1168.elb.eu-west-1.amazonaws.com',
                'emr_cluster': 'j-1GN53ARTWK3WB',
                'env_with_region': 'stage-eu-1',
                'env_level_with_region': 'stage-eu',
                'queue_prefix': 'stage-eu-1',
                'appd_name': '8363-STAGE-EU-1',
                'legacy_sqs_naming': '',
                'cdn_url': 'https://stage-cdn-eu.talech.com',
            },
            'prod-us-1': {
                'db_host': 'prod-us-webdb-main.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'pos_db_host': 'prod-us-posdb-main.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'pos_db_replica_1': 'prod-us-posdb-replica-01.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'pos_db_archive': 'prod-us-archivedb-main.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'pos_db': 'posstaging',
                'intsrv_db_host': 'prod-us-webdb-main.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'intsrv_db': 'intsrvprod',
                'scheduler_db_host': 'sched-prod-us.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'scheduler_db': 'schedulerDS',
                'oauth_db_host': 'prod-us-posdb-replica-01.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'oauth_db': 'oauth',
                'web_db_host': 'prod-us-webdb-main.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'web_db': 'website2',
                'old_cron_db_host': 'prod-us-webdb-main.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'old_cron_db': 'airflow',
                'web_cron_db_host': 'web-cron-nextgen-prod-us-1-db.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'web_cron_db': 'airflow',
                'metrix_airflow_db_host': 'metrix-airflow-prod-us-1-db.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'metrix_airflow_db': 'airflow',
                'iai_cron_db_host': 'iai-cron-db',
                'iai_cron_db': 'airflow-iai-cron',
                'iai_cron_feature_db_host': 'iai-cron-feature-db',
                'iai_cron_feature_db': 'airflow',
                'scheduler_airflow_db_host': 'sched1-airflow',
                'scheduler_airflow_db_name': 'db-sched1-airflow',
                'druid_db_host': 'druid-postgress-prod-us-1-db.cbj6fnelphl2.us-east-1.rds.amazonaws.com',
                'druid_db': 'druid',
                'payroll_db_host': 'payroll-postgres',
                'payroll_db': 'payroll_postgres',
                'web_redis_host': 'ec-prod-us-1.fptd2x.clustercfg.use1.cache.amazonaws.com',
                'iai_redis_host': 'iai-redis',
                'druid_broker_host': 'druid-query-prod-us-1-nlb-92602fc9450c0539.elb.us-east-1.amazonaws.com',
                'druid_router_host': 'router',
                'druid_middlemanager_host': 'middlemanager',
                'druid_historical_host': 'historical',
                'druid_coordinator_host': 'druid-master-prod-us-1-nlb-391de854334160d9.elb.us-east-1.amazonaws.com',
                'druid_storage_bucket': 'talech-prod-us-1-emr-us-east-1',
                'zookeeper_host': 'druid-master-prod-us-1-nlb-391de854334160d9.elb.us-east-1.amazonaws.com',
                'emr_cluster': 'j-29BRVCS60DAH5',
                'env_with_region': 'prod-us-1',
                'env_level_with_region': 'prod-us',
                'queue_prefix': 'prod-us-1',
                'appd_name': '4801-PROD',
                'legacy_sqs_naming': '',
                'cdn_url': 'https://cdn-us.talech.com',
            },
            'prod-eu-1': {
                'db_host': 'prod-eu-posdb-main.coezy0txbb3s.eu-west-1.rds.amazonaws.com',
                'pos_db_host': 'prod-eu-posdb-main.coezy0txbb3s.eu-west-1.rds.amazonaws.com',
                'pos_db_replica_1': 'prod-eu-posdb-replica-01.coezy0txbb3s.eu-west-1.rds.amazonaws.com',
                'pos_db_archive': 'prod-eu-posdb-replica-01.coezy0txbb3s.eu-west-1.rds.amazonaws.com',
                'pos_db': 'pos',
                'intsrv_db_host': 'prod-eu-posdb-main.coezy0txbb3s.eu-west-1.rds.amazonaws.com',
                'intsrv_db': 'intsrvprod_eu',
                'scheduler_db_host': 'prod-eu-posdb-main.coezy0txbb3s.eu-west-1.rds.amazonaws.com',
                'scheduler_db': 'schedulerDS',
                'oauth_db_host': 'prod-eu-posdb-replica-01.coezy0txbb3s.eu-west-1.rds.amazonaws.com',
                'oauth_db': 'oauth',
                'web_db_host': 'prod-eu-posdb-main.coezy0txbb3s.eu-west-1.rds.amazonaws.com',
                'web_db': 'website2',
                'old_cron_db_host': 'web-cron-prod-eu-1-db.coezy0txbb3s.eu-west-1.rds.amazonaws.com',
                'old_cron_db': 'airflow',
                'web_cron_db_host': 'web-cron-nextgen-prod-eu-1-db.coezy0txbb3s.eu-west-1.rds.amazonaws.com',
                'web_cron_db': 'airflow',
                'metrix_airflow_db_host': 'metrix-airflow-prod-eu-1-db.coezy0txbb3s.eu-west-1.rds.amazonaws.com',
                'metrix_airflow_db': 'airflow',
                'iai_cron_db_host': 'iai-cron-prod-eu-1-db.coezy0txbb3s.eu-west-1.rds.amazonaws.com',
                'iai_cron_db': 'iai_cron_prod_eu_1_db',
                'iai_cron_feature_db_host': 'iai-cron-feature-db',
                'iai_cron_feature_db': 'airflow',
                'scheduler_airflow_db_host': 'sched1-airflow',
                'scheduler_airflow_db_name': 'db-sched1-airflow',
                'druid_db_host': 'druid-postgress-prod-eu-1-db.coezy0txbb3s.eu-west-1.rds.amazonaws.com',
                'druid_db': 'druid',
                'payroll_db_host': 'payroll-postgres',
                'payroll_db': 'payroll_postgres',
                'web_redis_host': 'ec-prod-eu-1.o0iblk.clustercfg.euw1.cache.amazonaws.com',
                'iai_redis_host': 'iai-redis',
                'druid_broker_host': 'druid-query-prod-eu-1-nlb-7273fb393bb86d79.elb.eu-west-1.amazonaws.com',
                'druid_router_host': 'router',
                'druid_middlemanager_host': 'middlemanager',
                'druid_historical_host': 'historical',
                'druid_coordinator_host': 'druid-master-prod-eu-1-nlb-c8956411651e0bd4.elb.eu-west-1.amazonaws.com',
                'druid_storage_bucket': 'talech-prod-us-1-emr-eu-west-1',
                'zookeeper_host': 'druid-master-prod-eu-1-nlb-c8956411651e0bd4.elb.eu-west-1.amazonaws.com',
                'emr_cluster': 'j-2JY1MCZJXK57N',
                'env_with_region': 'prod-eu-1',
                'env_level_with_region': 'prod-eu',
                'queue_prefix': 'prod-eu-1',
                'appd_name': '8363-PROD',
                'legacy_sqs_naming': '',
                'cdn_url': 'https://cdn-eu.talech.com',
            },
        }
        
    @property
    def password_base64(self):
        return base64.b64encode(self.password.encode('utf8')).decode('utf8').replace('=', '')

    @property
    def api_token(self):
        try:
            return get_artifactory_api_key(cert=f'{self.base_dir}/USB_Global_Chain.crt', username=self.user, password=self.password)
        except:
            print_log_message(log_level='ERROR', msg=f'The Username or Password is Incorrect! Make sure you are using encrypted Artifactory password!')
            print_log_message(log_level='ERROR', msg=f'Check if your API key is generated in: https://artifactory.us.bank-dns.com/artifactory/webapp/#/profile') 
            print_log_message(log_level='ERROR', msg=f'Also try to regenerate API key in: https://artifactory.us.bank-dns.com/artifactory/webapp/#/profile')
            self.restore_backup_files_to_original()
            sys.exit(1)

    # def background(f):
    #     def wrapped(*args, **kwargs):
    #         return asyncio.get_event_loop().run_in_executor(None, f, *args, **kwargs)
    #     return wrapped

    def ecr_registry(self):
        return f'082280121301.dkr.ecr.{self.aws_region}.amazonaws.com'

    def get_git_hash(self, path):
        try:
            git_repo = git.Repo(path, search_parent_directories=True)
            sha = git_repo.head.commit.hexsha
            return git_repo.git.rev_parse(sha, short=8)
        except:   
            with open(f'{path}/.git/ORIG_HEAD') as file:
               return file.read()[-9:-1]

    def return_service_details(self):
        if self.use_local_variables_file:
            return self.talech_service, self.aws_logs_group, self.version, self.tag, self.ecr_url, self.expected_health_check_response_code, f'{self.local_variables_dir}/{self.local_variables_file}', self.environment_variables_from_secret
        else:
            return self.talech_service, self.aws_logs_group, self.version, self.tag, self.ecr_url, self.expected_health_check_response_code

    def get_git_branch(self, path):
        try:
            local_repo = git.Repo(path=path)
            return local_repo.active_branch.name
        except:
            try:
                if self.talech_service == 'talech' and path == self.webfe_source_code:
                        return os.environ['WEB_FE_BRANCH_NAME']
                elif self.talech_service == 'extsrv' and path == self.extsrv_fe_source:
                        return os.environ['FE_BRANCH_NAME']
                return os.environ['BRANCH_NAME']
            except:
                if self.talech_service == 'talech':
                    if path == self.webfe_source_code:
                        return os.environ[f'{self.fe_branch_name_variable_jenkins}']
                if self.talech_service == 'extsrv':
                    if path == self.extsrv_fe_source:
                        return os.environ[f'{self.fe_branch_name_variable_jenkins}']
                return os.environ[f'{self.branch_name_variable_jenkins}']

    def add_credentials(self, username, password):
        protocol = "https" if "https" in self.url else "http"
        hostname = urlparse(self.url).hostname
        return f"{protocol}://{username}:{password}@{hostname}"
    
    def backup_files_before_update(self):
        for file in self.list_of_files_to_update_creds:
            if os.path.exists(file):
                shutil.copy2(file, f'{file}_backup')

    def restore_backup_files_to_original(self):
        if os.path.exists(f'{self.path_to_dockerfile}/{self.dockerfile_name}_backup'):
            shutil.copy2(f'{self.path_to_dockerfile}/{self.dockerfile_name}_backup', f'{self.path_to_dockerfile}/{self.dockerfile_name}')
        for file in self.list_of_files_to_update_creds:
            if os.path.exists(file):
                shutil.copy2(f'{file}_backup', file)

    def update_credentials(self):
        for file in self.list_of_files_to_update_creds:
            if os.path.exists(file):
                print_log_message(log_level='INFO', msg=f'Updating credentials for: {file}')
                file_name = file.split('/')[-1]
    
                if file_name in ('composer.lock', 'package-lock.json', 'yarn.lock'):
                    self.replace_artifactory_url(file)
                    self.replace_artifactory_credentials(file)
    
                    if self.talech_service == 'talech' and file == f'{self.webfe_source_code}/yarn.lock':
                        base_dir = self.webfe_source_code
                    else:
                        base_dir = self.source_code
    
                    output = fill_in_data_to_template(base_dir=base_dir, filename=file, username=self.user, password=self.password, password_base64=self.password_base64, api_token=self.api_token)
                else:
                    self.replace_artifactory_credentials(file)
                    base_dir = '/'.join(file.split('/')[:-1])
                    output = fill_in_data_to_template(base_dir=base_dir, filename=file, username=self.user, password=self.password, password_base64=self.password_base64, api_token=self.api_token)
    
                write_data_to_file(filename=file, data=output)
    
    def replace_artifactory_url(self, file):
        replace_text_in_file(filename=file, search_text='https://artifactory.us.bank-dns.com/', replace_text='https://artifactory.us.bank-dns.com:5000/')
        replace_text_in_file(filename=file, search_text='https://artifactory.us.bank-dns.com:5000/', replace_text='https://{{ username }}:{{ password }}@artifactory.us.bank-dns.com:5000/')

    def copy_files_tree(self, src, dest):
        print_log_message(log_level='INFO', msg=f'Copying {src} to {dest}')
        if os.path.exists(dest):
            shutil.rmtree(dest)
            shutil.copytree(src, dest) 
        else:
            shutil.copytree(src, dest) 
    
    def replace_artifactory_credentials(self, file):
        replace_text_in_file(filename=file, search_text='_ARTIFACTORY_USER_', replace_text='{{ username }}')
        replace_text_in_file(filename=file, search_text='_ARTIFACTORY_TOKEN_BASE64_', replace_text='{{ password_base64 }}')
        replace_text_in_file(filename=file, search_text='_ARTIFACTORY_TOKEN_', replace_text='{{ password }}')
        replace_text_in_file(filename=file, search_text='_ARTIFACTORY_API_TOKEN_', replace_text='{{ api_token }}')

    def add_code_build_command(self):
        try:
            file_path = f'{self.path_to_dockerfile}/{self.dockerfile_name}'
            if os.path.exists(file_path):
                shutil.copy2(f'{file_path}', f'{file_path}_backup')
            print_log_message(log_level='INFO', msg=f'Updating Docker build command: {file_path}')
            replace_text_in_file(filename=file_path, 
                                 search_text='_REPLACE_WITH_BUILD_COMMAND_',
                                 replace_text=f'{self.code_build_command}')
            print_log_message(log_level='INFO', msg=f'Successfully updated build command in file {file_path}')
        except Exception as e:
            print_log_message(log_level='ERROR', msg=f'Error Occured During updating build command: {e}')
            self.restore_backup_files_to_original()
            sys.exit(1)

    def check_default_env_variables(self, single_call=True):
        missing_variables_list = []
        if os.path.exists(f'{self.source_code}/{self.default_env_variables}'):
            if isinstance(self.environment_variables_from_secret, list):
                for i in self.environment_variables_from_secret:
                    if i != '':
                        if isinstance(self.default_env_variables, list):
                            print_log_message(log_level='INFO', msg=f'Checking default evironment variables for {self.env}')
                            print_log_message(log_level='INFO', msg=f'Default variables list from: {self.default_env_variables[self.environment_variables_from_secret.index(i)]}')
                            print_log_message(log_level='INFO', msg=f'Environment variables list from secret: {i}')
                            missing_variables = default_env_variables_check(
                                base_dir=self.base_dir, 
                                path_to_default_vars_file=f'{self.source_code}/{self.default_env_variables[self.environment_variables_from_secret.index(i)]}', 
                                secret_name=f'{i}', 
                                region=self.aws_region
                                )
                        else:
                            print_log_message(log_level='INFO', msg=f'Checking default evironment variables for {self.env}')
                            print_log_message(log_level='INFO', msg=f'Default variables list from: {self.default_env_variables}')
                            print_log_message(log_level='INFO', msg=f'Environment variables list from secret: {i}')
                            missing_variables = default_env_variables_check(
                                base_dir=self.base_dir, 
                                path_to_default_vars_file=f'{self.source_code}/{self.default_env_variables}', 
                                secret_name=f'{i}', 
                                region=self.aws_region
                                )
                        for y in missing_variables:
                            missing_variables_list.append(y)
            else:   
                if self.environment_variables_from_secret != '':
                    print_log_message(log_level='INFO', msg=f'Checking default evironment variables for {self.env}')
                    print_log_message(log_level='INFO', msg=f'Default variables list from: {self.default_env_variables}')
                    print_log_message(log_level='INFO', msg=f'Environment variables list from secret: {self.environment_variables_from_secret}')
                    missing_variables = default_env_variables_check(
                        base_dir=self.base_dir, 
                        path_to_default_vars_file=f'{self.source_code}/{self.default_env_variables}', 
                        secret_name=self.environment_variables_from_secret, 
                        region=self.aws_region
                        )
                    for y in missing_variables:
                            missing_variables_list.append(y)
        else:
            print_log_message(log_level='WARN', msg=f'Missing file {self.default_env_variables}. Skipping check!')
        if single_call:
            if self.fail_on_missing_variables:
                self._fail_on_missing_variables(missing_variables_list)
        else:
            return missing_variables_list
        
    def _fail_on_missing_variables(self, missing_variables):
        if len(missing_variables) != 0:
            print_log_message(log_level='ERROR', msg=f'Not all default variables is set in environment!')
            print_log_message(log_level='ERROR', msg=f'Cannot proceed deployment!')
            self.restore_backup_files_to_original()
            sys.exit(1)

    def docker_image_already_exist(self):
        return check_if_docker_image_exists(registry=self.ecr_url, repository=self.docker_image_name, tag=self.version)
    
    def s3_upload(self, filename, bucket, path):
        s3_path = f's3://{bucket}/{path}'
        print_log_message(log_level='INFO', msg=f'Uploading {filename} to {s3_path}')
        try:
            upload_file(file_name=filename, bucket=bucket, object_name=path)
            print_log_message(log_level='INFO', msg=f'Upload successful!')
        except Exception as e:
            print_log_message(log_level='ERROR', msg=f'Upload failed with error: {e}')
            self.restore_backup_files_to_original()
            sys.exit(1)

    def print_environment_build_info(self):
        log_messages = [
            f'STARTING DOCKER IMAGE BUILD',
            f'ENVIRONMET: {self.env}',
            f'PRODUCT: {self.product_name}',
            f'CODE BRANCH: {self.get_git_branch(self.source_code)}',
        ]

        if self.product_name == 'talech':
            log_messages.append(f'WEB-FE BRANCH: {self.get_git_branch(self.webfe_source_code)}')

        log_messages.extend([
            f'USE LOCAL VARIABLES: {self.use_local_variables_file}',
            f'FORCE REBUILD: {self.force_rebuild}',
            'Starting pre-build steps',
            'Creating build directories',
        ])

        for message in log_messages:
            print_log_message(log_level='INFO', msg=message)

    def stage_level_environment_deployment_preparation(self):
        print_log_message(log_level='INFO', msg=f'Creating docker-compose.yml for {self.env}')
        dc_output = fill_in_docker_compose_template(
            base_dir=self.template_location,
            filename=self.template_name,
            ecr_url=self.ecr_url,
            product_name=self.docker_image_name,
            product_version=self.version,
            tag=self.tag,
            aws_logs_group=self.aws_logs_group,
            environment_name=self.env
        )

        compose_file = f'{self.buid_dir}/docker-compose.yml'
        write_to_docker_compose_file(filepath=compose_file, output=dc_output)
        if self.use_local_variables_file:
            shutil.copy2(f'{self.templates_base_dir}/deploy.sh', f'{self.buid_dir}/deploy.sh')
        else:
            shutil.copy2(f'{self.templates_base_dir}/deploy_old_way.sh', f'{self.buid_dir}/deploy.sh')
        print_log_message(log_level='INFO', msg=f'Creating archive: current.zip')
        archive_current_zip(f'{self.output}/current', f'{self.base_dir}/build/')

    def build_docker_image(self):
        print_log_message(log_level='INFO', msg='Starting build steps')
        image_name = f'{self.default_ecr_registry}/{self.product_name}:{self.version}'
        print_log_message(log_level='INFO', msg=f'Docker image {image_name} build in progress...')
        print_log_message(log_level='INFO', msg='Docker image build might take a while, please wait...')
        try:
            if build_docker_image(path_to_dockerfile=self.path_to_dockerfile, docker_build_command=self.docker_build_command) == 0:
                print_log_message(log_level='INFO', msg=f'Docker image {image_name} successfully built')
            else:
                print_log_message(log_level='ERROR', msg=f'Docker image {image_name} build failed with error')
                self.restore_backup_files_to_original()
                sys.exit(1)
        except Exception as e:
            print_log_message(log_level='ERROR', msg=f'Docker image {image_name} build failed with error: {e}')
            self.restore_backup_files_to_original()
            sys.exit(1)

    # @background
    def push_docker_image(self):
        if not self.build_only:
            print_log_message(log_level='INFO', msg=f'Starting push Docker image {self.tag} to ECR... Please wait...')
            try:
                push_docker_image(f'{self.tag}')
                print_log_message(log_level='INFO', msg=f'Docker image {self.product_name}:{self.version} successfully pushed to ECR')
            except Exception as e:
                print_log_message(log_level='ERROR', msg=f'Error Occured During push Docker image {self.tag} to ECR: {e}')
                self.restore_backup_files_to_original()
                sys.exit(1)                

    def create_version_txt(self):
        version_path = f'{self.output}/version.txt'
        try:
            with open(version_path, 'w') as f:
                f.write(f'{self.version}')
            print_log_message(log_level='INFO', msg=f'Successfully wrote version {self.version} to {version_path}')
        except Exception as e:
            print_log_message(log_level='ERROR', msg=f'Error Occured During creating version.txt: {e}')
            self.restore_backup_files_to_original()
            sys.exit(1)

    def update_aws_asg(self):
        print_log_message(log_level='INFO', msg=f'Starting updating AWS ASG')
        try:
            if self.talech_service == 'old-data-etls':
                deployment_new_dev_asg(asg_group_name=f'asg-{self.env}')
            else:
                deployment_new_images_asg(asg_group_name=f'asg-{self.env}')
            print_log_message(log_level='INFO', msg=f'AWS ASG update done')
        except Exception as e:
            print_log_message(log_level='ERROR', msg=f'AWS ASG update failed with error: {str(e)}')

    def prepapre_environment_variables_file(self):
        list_of_environment_specifics = {
            'environment': self.env,
            'only_env_name': self.env_stage,
            'env_with_region': self.local_variables_file_fill_values[self.env_stage]['env_with_region'],
            'env_level_with_region': self.local_variables_file_fill_values[self.env_stage]['env_level_with_region'],
            'aws_region': self.aws_region,
            'oauth_db_host': self.local_variables_file_fill_values[self.env_stage]['oauth_db_host'],
            'oauth_db_name': self.local_variables_file_fill_values[self.env_stage]['oauth_db'],
            'pos_db_host': self.local_variables_file_fill_values[self.env_stage]['pos_db_host'],
            'pos_db_replica_1': self.local_variables_file_fill_values[self.env_stage]['pos_db_replica_1'],
            'pos_db_archive': self.local_variables_file_fill_values[self.env_stage]['pos_db_archive'],
            'pos_db_name': self.local_variables_file_fill_values[self.env_stage]['pos_db'],
            'intsrv_db_host': self.local_variables_file_fill_values[self.env_stage]['intsrv_db_host'],
            'intsrv_db_name': self.local_variables_file_fill_values[self.env_stage]['intsrv_db'],
            'scheduler_db_host': self.local_variables_file_fill_values[self.env_stage]['scheduler_db_host'],
            'scheduler_db_name': self.local_variables_file_fill_values[self.env_stage]['scheduler_db'],
            'web_db_host': self.local_variables_file_fill_values[self.env_stage]['web_db_host'],
            'web_db_name': self.local_variables_file_fill_values[self.env_stage]['web_db'],
            'old_cron_db_host': self.local_variables_file_fill_values[self.env_stage]['old_cron_db_host'],
            'old_cron_db_name': self.local_variables_file_fill_values[self.env_stage]['old_cron_db'],
            'web_cron_db_host': self.local_variables_file_fill_values[self.env_stage]['web_cron_db_host'],
            'web_cron_db_name': self.local_variables_file_fill_values[self.env_stage]['web_cron_db'],
            'metrix_airflow_db_host': self.local_variables_file_fill_values[self.env_stage]['metrix_airflow_db_host'],
            'metrix_airflow_db_name': self.local_variables_file_fill_values[self.env_stage]['metrix_airflow_db'],
            'iai_cron_db_host': self.local_variables_file_fill_values[self.env_stage]['iai_cron_db_host'],
            'iai_cron_db_name': self.local_variables_file_fill_values[self.env_stage]['iai_cron_db'],
            'iai_cron_feature_db_host': self.local_variables_file_fill_values[self.env_stage]['iai_cron_feature_db_host'],
            'iai_cron_feature_db_name': self.local_variables_file_fill_values[self.env_stage]['iai_cron_feature_db'],
            'scheduler_airflow_db_host': self.local_variables_file_fill_values[self.env_stage]['scheduler_airflow_db_host'],
            'scheduler_airflow_db_name': self.local_variables_file_fill_values[self.env_stage]['scheduler_airflow_db_name'],
            'druid_db_host': self.local_variables_file_fill_values[self.env_stage]['druid_db_host'],
            'druid_db_name': self.local_variables_file_fill_values[self.env_stage]['druid_db'],
            'druid_broker_host': self.local_variables_file_fill_values[self.env_stage]['druid_broker_host'],
            'druid_router_host': self.local_variables_file_fill_values[self.env_stage]['druid_router_host'],
            'druid_middlemanager_host': self.local_variables_file_fill_values[self.env_stage]['druid_middlemanager_host'],
            'druid_historical_host': self.local_variables_file_fill_values[self.env_stage]['druid_historical_host'],
            'druid_coordinator_host': self.local_variables_file_fill_values[self.env_stage]['druid_coordinator_host'],
            'druid_storage_bucket': self.local_variables_file_fill_values[self.env_stage]['druid_storage_bucket'],
            'zookeeper_host': self.local_variables_file_fill_values[self.env_stage]['zookeeper_host'],
            'emr_cluster': self.local_variables_file_fill_values[self.env_stage]['emr_cluster'],
            'queue_prefix': self.local_variables_file_fill_values[self.env_stage]['queue_prefix'].replace('-', '_'),
            'appd_name': self.local_variables_file_fill_values[self.env_stage]['appd_name'],
            'payroll_db_host': self.local_variables_file_fill_values[self.env_stage]['payroll_db_host'],
            'payroll_db_name': self.local_variables_file_fill_values[self.env_stage]['payroll_db'],
            'redis_host': self.local_variables_file_fill_values[self.env_stage]['web_redis_host'],
            'iai_redis_host': self.local_variables_file_fill_values[self.env_stage]['iai_redis_host'],
            'legacy_sqs_naming': self.local_variables_file_fill_values[self.env_stage]['legacy_sqs_naming'],
            'cdn_url': self.local_variables_file_fill_values[self.env_stage]['cdn_url'],
        }
    
        if self.product_name in ['metrix-druid-master', 'metrix-druid-query', 'metrix-druid-data']:
            shutil.copy2(f'{self.local_variables_dir}/{self.local_variables_file_1}', f'{self.local_variables_dir}/{self.local_variables_file_1}_backup')
            shutil.copy2(f'{self.local_variables_dir}/{self.local_variables_file_2}', f'{self.local_variables_dir}/{self.local_variables_file_2}_backup')
            fill_in_environment_variables_template(self.local_variables_dir, self.local_variables_file_1, env_list = list_of_environment_specifics)
            fill_in_environment_variables_template(self.local_variables_dir, self.local_variables_file_2, env_list = list_of_environment_specifics)
            underscored_product_name=self.product_name.replace('-', '_')
            print_log_message(log_level='INFO', msg=f'Moving {self.local_variables_file_1} to {self.buid_dir}/{underscored_product_name}_1_envvars')
            shutil.copy2(f'{self.local_variables_dir}/{self.local_variables_file_1}', f'{self.buid_dir}/{underscored_product_name}_1_envvars')
            print_log_message(log_level='INFO', msg=f'Moving {self.local_variables_file_2} to {self.buid_dir}/{underscored_product_name}_2_envvars')
            shutil.copy2(f'{self.local_variables_dir}/{self.local_variables_file_2}', f'{self.buid_dir}/{underscored_product_name}_2_envvars')
            shutil.copy2(f'{self.local_variables_dir}/{self.local_variables_file_1}_backup', f'{self.local_variables_dir}/{self.local_variables_file_1}')
            shutil.copy2(f'{self.local_variables_dir}/{self.local_variables_file_2}_backup', f'{self.local_variables_dir}/{self.local_variables_file_2}')
        else:
            shutil.copy2(f'{self.local_variables_dir}/{self.local_variables_file}', f'{self.local_variables_dir}/{self.local_variables_file}_backup')
            fill_in_environment_variables_template(self.local_variables_dir, self.local_variables_file, env_list = list_of_environment_specifics)
            underscored_product_name=self.product_name.replace('-', '_')
            print_log_message(log_level='INFO', msg=f'Moving {self.local_variables_file} to {self.buid_dir}/{underscored_product_name}_envvars')
            shutil.copy2(f'{self.local_variables_dir}/{self.local_variables_file}', f'{self.buid_dir}/{underscored_product_name}_envvars')
            shutil.copy2(f'{self.local_variables_dir}/{self.local_variables_file}_backup', f'{self.local_variables_dir}/{self.local_variables_file}')
        if self.level in ['stage', 'prod']:
            if self.product_name == 'talech':
                for file in os.listdir(self.local_variables_dir):
                    if '.php' in file:
                        src_file = os.path.join(self.local_variables_dir, file)
                        dst_file = os.path.join(self.buid_dir, file)
                        shutil.copy2(src_file, dst_file)

    def prepare_secrets_download_script(self):
        self.dict_of_secrets[self.talech_service] ={
            'file_name': f'{self.talech_service.replace("-", "_")}_secrets', 
            'secret_name': self.environment_variables_from_secret
        }
        shutil.copy2(f'{self.templates_base_dir}/secrets_download.py', f'{self.templates_base_dir}/secrets_download.py_backup')
        secrets_download_file_preparation(self.templates_base_dir, 'secrets_download.py', dict_of_secrets=self.dict_of_secrets, aws_region=self.aws_region)
        shutil.copy2(f'{self.templates_base_dir}/secrets_download.py', f'{self.buid_dir}/secrets_download.py')
        shutil.copy2(f'{self.templates_base_dir}/secrets_download.py_backup', f'{self.templates_base_dir}/secrets_download.py')
        print_log_message(log_level='INFO', msg=f'secrets_download.py scripts are prepared')

    def rewrite_envvars_file(self):
        underscored_product_name=self.product_name.replace('-', '_')
        if len(self.rewrite_variables_list) > 0:
            for i in self.rewrite_variables_list:
                variable, value = i.split('=')
                with open(f'{self.buid_dir}/{underscored_product_name}_envvars', 'r+') as f:
                    lines = f.readlines()
                    for y, line in enumerate(lines):
                        if line.startswith(variable + '='):
                            lines[y] = variable + '=' + value + '\n'
                            break
                    f.seek(0)
                    f.writelines(lines)
                    f.truncate()

    def docker_image_build(self):
        self.print_environment_build_info()
        self.backup_files_before_update()
        self.update_credentials()
        self.add_code_build_command()
        if self.use_local_variables_file:
            self.prepapre_environment_variables_file()
            if self.level in ['stage', 'prod']:
                self.rewrite_envvars_file()
                self.prepare_secrets_download_script()
        self.build_or_skip_docker_image()
        self.restore_backup_files_to_original()
        if self.should_deploy():
            self.stage_level_environment_deployment_preparation()
            self.create_version_txt()
            self.upload_zip_to_s3()
            self.update_aws_asg()
            self.check_default_env_variables()
            self.perform_health_check()
    
    def build_or_skip_docker_image(self):
        if self.should_build_docker_image():
            buildstartTime = datetime.datetime.now()
            self.update_credentials()
            self.add_code_build_command()
            self.build_docker_image()
            print_log_message(log_level='INFO', msg=f'Build took: {datetime.datetime.now() - buildstartTime}')
            if not self.build_only:
                self.push_docker_image()
        else:
            print_log_message(log_level='INFO', msg=f'Docker image {self.product_name}:{self.version} already exists in ECR')
            print_log_message(log_level='INFO', msg=f'Skipping Docker image build')
    
    def should_build_docker_image(self):
        return self.force_rebuild or not self.docker_image_already_exist()
    
    def should_deploy(self):
        return self.level in ['stage', 'prod'] and not self.build_only
    
    def upload_zip_to_s3(self):
        self.s3_upload(filename=f'{self.output}/current.zip', bucket=f'{self.deployment_s3_bucket}', path=f'{self.deployment_bucket_dir}/{self.env}/current.zip')
        self.s3_upload(filename=f'{self.output}/version.txt', bucket=f'{self.deployment_s3_bucket}', path=f'{self.deployment_bucket_dir}/{self.env}/version.txt')
        self.s3_upload(filename=f'{self.output}/current.zip', bucket=f'{self.deployment_s3_bucket}', path=f'{self.deployment_bucket_dir}/{self.env}/history/{self.version}.zip')
    
    def perform_health_check(self):
        if self.url is None:
            print_log_message(log_level='INFO', msg=f'No health check is set for this build')
            return
        url = [self.url if 'druid' in self.product_name else self.url]
        list_of_resp, list_of_err = check_url_health(urls=url, basedir=self.base_dir, expected_response_code=self.expected_health_check_response_code)
        for key, value in list_of_resp.items():
            if list_of_err[key] == 200:
                print_log_message(log_level='INFO', msg=f'{value}')
            else:
                print_log_message(log_level='ERROR', msg=f'{value}')
        if all(value == 200 for value in list_of_err.values()):
            print_log_message(log_level='INFO', msg=f'Health Check is OK!')
        else:
            print_log_message(log_level='ERROR', msg=f'Health Check Failed!')
            sys.exit(1)
