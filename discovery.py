import yaml
try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader
from pathlib import Path
import pprint
import logging
from deployment import DeploymentGroups
import os
import copy
import sys



logger = logging.getLogger('discovery')

def get_deployment_groups(config):
    '''
    main func
    Parses yaml files and returns struct 'deployment groups'
    Example data for ansible 'vars:':
        vars:
            <deployment_task>:
                deployment_groups:
                    - dg: domain.ru_year #REQUIRED
                      tags: ['tag1','tag2'] #REQUIRED
                      args: ['arg1', 'arg2']
    returned data from  _find_deployment_groups()
    '''
    yaml_files = _find_yaml_files(config)
    raw_deployment_groups = _find_deployment_groups(yaml_files, config)
    deployment_groups = DeploymentGroups(raw_deployment_groups, config)
    return deployment_groups

def _find_deployment_groups(yaml_files, config):
    # Getting deployment groups from yaml files
    '''
    yaml_files: set | list
    config: dict

    Returned :
    { 
        '<deployment_group': {
            '<deployment_task>': [
                {
                    'dg': <deployment_group>,
                    'tags': ['tag1', 'tag2'] ,
                    'args': ['arg1', 'arg2'],
                    'playbook': '/home/user/ansible/.../playbook.yml',
                    ....
                },
            ],
        },
    }

    '''
    logger.info('Parsing yaml files...')
    deployment_tasks = config['deployment_tasks']
    deployment_groups = {}
    for yaml_file in yaml_files:
        yaml_data = read_yaml(yaml_file, config, pass_errors=True)
        if not yaml_data:
            continue
        for hosts_item in yaml_data:
            if not isinstance(hosts_item, dict) or 'vars' not in hosts_item:
                continue
            if not hosts_item['vars']:
                continue
            elif 'hosts' not in hosts_item:
                continue
            if '_vars_files' in hosts_item['vars']:
                for vars_file in hosts_item['vars_files']:
                    if not vars_file.startswith('/'):
                        vars_file = vars_file.split('/')
                        #Берет директорию где лежит плейбук и подставляет в корень vars файла
                        vars_file = yaml_file.split('/')[:-1] + vars_file
                        vars_file = '/'.join(vars_file)
                    hosts_item['vars'].update(read_yaml(vars_file, config))
            if not hosts_item.get('vars',None):
                continue
            hosts = hosts_item['hosts']
            tasks_data = _parse_hosts_vars(config,
                                          hosts_item['vars'],
                                          deployment_tasks,
                                          playbook=yaml_file,
                                          hosts=hosts)
            if tasks_data:
                _update_deployment_groups(tasks_data, deployment_groups)
    return deployment_groups 
    
def _parse_hosts_vars(config, hosts_vars, deployment_tasks, playbook, **kwargs):
    """
    config: dict 
    hosts_vars: dict - (vars: from ansible hosts' set)
    deployment_tasks: set | list -  available deployment group's names
    playbook: string  - path to playbook
    kwargs : kwargs  - variables for -e flag in ansible-playbook

    Finds tasks in 'vars:' and returns:
    {
        '<task>': [ 
                    {
                        'dg': 'domain.ru_year',
                        'tags': ...,
                        ...
                     },
                ],
        '<task>': [{}],
        ...
    }
    """
    if isinstance(hosts_vars, list):
        return
    result = {}
    tasks_data = []
    #Поиск DT
    for dt in deployment_tasks:
        if dt in hosts_vars:
            tasks_data.append((dt, hosts_vars[dt]))
    global_dg = hosts_vars.get('_deployment_groups', None)
    #Парсинг DT
    for dt, data in tasks_data:
        if not data:
            message = "Error. Task '{}' has no data, file: {}"
            message = message.format(dt, playbook)
            logger.error(message)
            if config.get('debug'):
                raise Exception(message)
            else:
                sys.exit(1)
        if dt not in result:
            result[dt] = []
        if 'deployment_groups' not in data and not global_dg:
            message = "Metadata format is invalid. deployment_groups not found in task '{}', file {}"
            logger.warning(message.format(dt, playbook))
            continue
        elif global_dg:
            message = "Warning, global deployment groups used. File: {}"
            logger.debug(message.format(playbook))
            data['deployment_groups'] = global_dg
        global_args = data.get('args', None)
        global_tags = data.get('tags', None)
        # Adding global args
        if global_tags:
            logger.debug("Warning, global ansible tags used. File {}".format(playbook))
        if global_args:
            logger.debug("Warning, global ansible args used. File {}".format(playbook))
        for dg_original in data['deployment_groups']:
            dg = copy.deepcopy(dg_original)
            if not 'args' in dg:
                dg['args'] = []
            # Adding cli args
            if len(config['environment']) > 0:
                dg['args'] += config['environment']
            # Adding from kwargs
            for key,value in kwargs.items():
                dg[key] = value
            dg['playbook'] = playbook
            if data.get('nolimit', False):
                dg['hosts'] = None
            if config['limit']:
                dg['hosts'] = config['limit']
            if global_args:
                dg['args'] += global_args
            if global_tags:
                if not 'tags' in dg:
                    dg['tags'] = []
                dg['tags'] += global_tags
            if not 'dg' in dg:
                message = "Metadata format is invalid. 'dg' key not found in deployment task: '{}', file{}"
                logger.warning(message.format(dt, playbook))
                logger.debug(dg)
                continue
            if not 'tags' in dg and not dg.get('tags', None) and not data.get('notags', False):
                message = "Metadata format is invalid. 'tags' key not found in deployment group: '{}', файл {}"
                logger.warning(message.format(dt, playbook))
                logger.debug(dg)
                continue
            #Магия. Добавление всех items DG как environment для запуска плейбука
            for key, value in dg.items():
                if key in ("args","tags","hosts","playbook"):
                    continue
                if len(str(value).split(' ')) > 0:
                    dg['args'].append('-e \'{}="{}"\''.format(key,value))
                else:
                    dg['args'].append('-e "{}={}"'.format(key,value))

            result[dt].append(dg)
    return result

def _update_deployment_groups(tasks_data, deployment_groups):
    #Modifying dictionary 'deployment_grous', merging with _parse_hosts_vars
    #Description of 'deployment_groups' format  in function _find_deployment_groups
    for task, _deployment_groups in tasks_data.items():
        for deployment_group in _deployment_groups:
            dg_name = deployment_group['dg']
            if dg_name not in deployment_groups:
                deployment_groups[dg_name] = {}
            if task not in deployment_groups[dg_name]:
                deployment_groups[dg_name][task] = []
            deployment_groups[dg_name][task].append(deployment_group)
    return deployment_groups


def _find_yaml_files(config):
    #Finding all files in config['root_dir'] with extensions from config['extensions'] 
    root_dir = config.get('root_dir')
    if not root_dir:
        root_dir = "~/ansible-ng"
    extensions = ['.yml', '.yaml']
    if root_dir.startswith('~/'):
        root_dir = Path(root_dir).home().joinpath(root_dir[2:])
    logger.info("Search for files in {} with extensions '{}'".format(root_dir, extensions))
    finded_files = []
    for extension in extensions:
        extension = "**/*{}".format(extension)
        finded_files += [str(x) for x in Path(root_dir).glob(extension)]
    finded_files = [x for x in finded_files if os.path.isfile(x)]
    return finded_files


def open_file(path):
    src = ""
    with open(str(path), 'r') as stream:
        try:
            return stream.read()
        except Exception as e:
            logging.error('Error while open file {}: {}'.format(path), str(e))


def _is_gron_file(file_src, config):
    required_strings = config['deployment_tasks'] + ['_vars_files',]
    for task in required_strings:
        if task in file_src:
            return True
    return False



def read_yaml(path, config=None, pass_errors=False):
    logger.debug('Open {}'.format(path))
    file_src = open_file(path)
    if not file_src:
        return
    if config:
        if not _is_gron_file(file_src, config):
            logger.debug("{} is not gron file, skip".format(path))
            return
    try:
        return yaml.load(file_src, Loader=Loader)
    except yaml.YAMLError as e:
        if not pass_errors:
            raise e
        else:
            logging.error('Ошибка при открытии файла {}: {}'.format(path), str(e))
