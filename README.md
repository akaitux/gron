
# GRON

The tool to automatically search and launch a group of ansible playbooks. Currently used to roll out certificates, but in theory it can be used for anything that requires running a group of playbooks.

## Installation

```
pip3 install -r requirements.txt
```


## Definitions 

***Deployment Group*** - a identificator that concatenates playbooks. In this case, it contains the domain name and additional data specified with an underscore (eg domain.ru_letsencrypt). In other words, the deployment group is an identifier that links playbooks that roll out the same certificate. If we tell gron to run playbooks from the specified DG and roll out certificates using them, then these playbooks should roll out the same certificate to all their servers.

***Deployment Task*** - a string indicating the type of task that DG runs. For example, _deploy_cert - to roll out the certificate, _certbot_acme - to execute the acme challenge. These commands are hardcoded (TODO).

## Description

The program searches for all yaml files, selects those that look like playbooks (valid yaml files that contain hosts elements and that contain special deployment tasks variables), and then runs them as playbooks with the specified arguments and tags. It is necessary for grouping tasks in different playbooks, for example, those responsible for rolling out a specific certificate.

Get current metadata from files and output in yaml format

```bash
#Show all metadata
gron -s --root-dir /home/user/ansible-ng
#Show only deployment groups
gron -sg --root-dir /home/user/ansible-ng
```



An example of configuring the deployment of a certificate by launching a playbook with a certs tag and an argument  '-e variable=VARIABLE': 

```yaml
- hosts: someserver.domain.ru
  vars:
    _deploy_cert:                               # <-- deployment task
      deployment_groups:
        - dg: domain.ru_year					# <-- deployment group 
          tags: ['certs']                       # <-- playbook's tags
          args: ['-e','variable="VARIABLE"']    # <-- additional variables   
          variable: "VARIABLE"                  # <-- addtiional variables too (analog -e variable="VARIABLE").
```

You can also load variables using vars_files, and all variables from each file will be added to vars.

Example:

```yaml
- hosts: someserver.domain.ru
  vars:
    _vars_files: yes # If this variable is present with any value, files from vars_files will be loaded
  vars_files:
      - '../vars/gron.yml' # If there is no leading / (the path is relative), then the path to the playbook will be substituted instead of the first part of the path (here ..)
```
    

In each playbook that is responsible for rolling out the annual domain.ru certificate, you must specify Deployment Group `domain.ru_year` with task `_deploy_cert` and then Gron, finding them, will start sequentially. In order for the certificate to be guaranteed to be the same on all these hosts, you need to take it from Vaut.

You can specify ***Global variables*** - _deployment_groups, tags, args.

If you specify ***_deployment_groups*** vars root, then all groups will participate in each task.

For example, all groups from ***_deployment_groups*** will be used in tasks ***_certbot_acme, _certbot_upload, _deploy_cert***:

```yaml
- hosts: "some-hosts"
  vars:
    _certbot_acme:
      tags: ['acme_challenge']
      nolimit: true
      deployment_groups: "#GLOBAL"
    _certbot_upload:
      tags: ['certbot_upload']
      nolimit: true
      deployment_groups: "#GLOBAL"
    _deploy_cert:
      tags: ['gcore_upload']
      nolimit: true
      deployment_groups: "#GLOBAL"
    _deployment_groups:
      - dg: 'domain1.ru_letsencrypt'
        domains: ['domain1.ru','*.domain1.ru']
      - dg: 'domain2.ru_letsencrypt'
        domains: ['domain2.ru','*.domain2.ru']
```

If you specify tags and args inside a DT, then the arguments and tags will be applied to each DG that participates in the task.

Example:

```yaml
- hosts: "someserver.domain.ru"
  vars:
    _deploy_cert:
      tags: ['nginx_conf']
      args: ['-C', '-vvvv']
      deployment_groups:
        - dg: domain1.ru_letsencrypt
        - dg: domain2.ru_letsencrypt

#Аналогично
- hosts: "someserver.domain.ru"
  vars:
    _deploy_cert:
      deployment_groups:
        - dg: domain1.ru_letsencrypt
          tags: ['nginx_conf']
          args: ['-C', '-vvvv']
        - dg: domain2.ru_letsencrypt
          tags: ['nginx_conf']
          args: ['-C', '-vvvv']
```

The following flags are also supported:

    nolimit - don't set the -l 'hosts' argument when starting the playbook. Needed to run on localhost
    notags - allow launch without specifying roll tags. By default, the playbook cannot be started without them.

Example:

```yaml
- hosts: 127.0.0.1
  vars:
    _deploy_cert:
      nolimit: yes
      notags: yes
      deployment_groups:
        - dg: domain1.ru_letsencrypt
```

All variables specified inside the Deployment group, except args, tags, hosts, playbook, will be passed to the playbook launch command via the -e arguments

Example:

```yaml
- hosts: 127.0.0.1
  vars:
    _certbot_acme:
      tags: ['acme_dns']
      nolimit: true
    _deployment_groups:
      - dg: 'domain1.ru_letsencrypt'
        zone_file: "/etc/namedb/master/domain1.ru"
```

This will launch a playbook with arguments:

```bash
ansible-playbook ... -t acme_dns -e 'zone_file=/etc/namedb/master/domain1.ru' 
```

