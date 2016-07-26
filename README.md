# zkconfgen
Generate configuration files (for nginx, apache, haproxy, etc.) from Zookeeper registered services using file templates.
This program watches for changes in Zookeeper (using triggers), immediately re-generates all defined output config files and calls specified
reload command to apply the new configuration.

Features
==================
* files are generated using jinja2 templates (means that zkconfgen can generate config file for virtually any program)
* triggers are set on all node paths so any change will be detected (and acted on) immediately
* originally developed for dropwizard nodes, but it's flexible and configurable to work with any source that can write to Zookeeper
* can watch multiple paths in parallel (e.g. dev, test, prod)
* can generate multiple files from one Zookeeper listing
* output can be altered using includepath_regex/excludepath_regex before it is submited to file templating engine
* includepath_regex/excludepath_regex can be specified per generated file separately so you can easily create e.g. DMZ service with limited service list
* custom variables can be injected to the templating engine separately per every output file
* can check configuration validity before calling reload command so it will not screw the running service
* reload command run can be delayed specified number of seconds after detecting the change so the excessive changes in the Zookeeper nodes will not trigger reload too frequently (reload might be an expensive operation for some applications)
* zkconfgen configuration can be reloaded using signal (SIGUSR1) and that will also trigger a full refresh of the Zookeeper tree and check for output files freshness (means you can trigger a manual refresh if you have altered some template files or you just want to make absolutely sure that everything is up to date)
* with higher loglevel, you can see actual diffs of all changed files
* zkconfgen automatically decodes json payload from dropwizard services and you can use it in the templating
* all Zookeeper requests are handled asynchronously so even the high number of changes (combined with connection timeout handling) is processed without blocking (and long running reloads do not affect watching for triggers)

How does it work
==================
After the start, zkconfgen reads its own config file and determines which paths should be watched over. Then it connects to the Zookeeper
ensemble, lists the current node status and sets all required watches so we will be informed about every change in the Zookeeper tree. Right after that, the program
checks if there's need to update some output config files (that were left over when the program had run the last time) or to write fresh new files.
If there were some changes, check command will be called to verify consistency of the newly generated files. If check succeeds, reload command is called (if defined)
to finally apply new configuration.
After that (now all files are up to date), it just waits for any change and if the change in Zookeeper tree results in change of any output files, the
check-and-reload process is repeated.

How to install it
==================
Manual install - execute as root:
```
git clone https://github.com/YanChii/zkconfgen .
cp zkconfgen /usr/bin/zkconfgen
chmod 755 /usr/bin/zkconfgen
mkdir -p /etc/zkconfgen/templates
cp zkconfgen.ini.sample /etc/zkconfgen/zkconfgen.ini
cp -r examples /etc/zkconfgen
```
And if you have systemd:
```
cp zkconfgen.service /etc/systemd/system/zkconfgen.service
systemctl daemon-reload
```
How to run it
==================
First, you need to have properly configured ini file and template(s) (see next sections).

Simply from the command line:
```
/usr/bin/zkconfgen
```
Or with custom config and logfile:
```
/usr/bin/zkconfgen -c /etc/zkconfgen/zkconfgen.ini -l /tmp/zkconfgen.log
```
Or to see what options from config can be overrided:
```
/usr/bin/zkconfgen -h
```
Or, with systemd .service file in place:
```
systemctl start zkconfgen
systemctl status zkconfgen
systemctl enable zkconfgen
```

Basic config
==================
The main config file (zkconfgen.ini) is well documented an you will (hopefully) get the idea quickly. But for the impatient, this is minimum to be set:
```
[main]														#	The [main] section is the only required section. But I recommend also at leas 1 file section.
zk_servers = here.go.zookeeper.ips
zk_watch_paths = /dev/service								# 	This is most important part. This is path (or more paths) to look at when generating config files.
															#	The idea is this: <zk_watch_path>/<service_name>/<service_instance_list>
															#	For dropwizard, it is like /dev/service/myservice/b4eaecea-99e5-4f14-8c53-e35adb34bcd2
															#	
reload_command = /sbin/nginx -s reload						#	If you want to reload multiple programs, put them into a script.
															# 	But remember to properly handling all return values
															#	(otherwise you will fool the zkconfgen that the reload went ok when it actually hasn't).

[nginx.conf]												#	The name of the section is only for your information. It does not really affect anything.
infile = /etc/zkconfgen/templates/nginx.conf.jinja			#	Need to look also into this template to check if it matches your needs.
outfile = /etc/nginx/nginx.conf
```

Working with templates
==================
This is the last but very important part. By templating you change a list of services (actually a python dict) into a config file.
It's done by iterating over the list (dict). I'll show you how.

When you use config file for nginx from the above example, I recommend to use templates/nginx.conf.jinja.
But after reading this section, you'll be able to write any template you like.

I'll explain the main variables you can use. It's just two of them:
* ZK_TREE
* PUSHENV
The first one contains the whole view of Zookeeper tree and this is mostly all you need. The other one (PUSHENV) contains custom environment that you
have set in the ini file. In our zkconfgen.ini above, there is no such variable and therefore PUSHENV variable will be empty.

Let's see how we can use ZK_TREE.
It is just plain (alphabetically ordered) nested python dict. The first level contains just paths you've specified in zk_watch_paths.
Example: we've specified in zkconfgen.ini this:
```
[main]
zk_watch_paths = /dev/service,/test/service,/prod/service
...
```
then the first level of ZK_TREE will be (written in python): ZK_TREE.keys() -> ['/dev/service', '/test/service', '/prod/service'].
In the lower layer (by the lower layer I mean for example ZK_TREE['/dev/service']), there is list of service names. And under that (means for example
ZK_TREE['/dev/service']['myservice']), there is instance list.
Example 2: to access a content of the Zookeeper node /test/service/myservice/b4eaecea-99e5-4f14-8c53-e35adb34bcd2 you want to write
```
ZK_TREE['/dev/service']['myservice']['b4eaecea-99e5-4f14-8c53-e35adb34bcd2']
```

And now let's iterate over it so we can get all services we have:
```
{%- for zk_watch_path in ZK_TREE -%}
This is list of services in path {{zk_watch_path}}:
{% for svcname in ZK_TREE[zk_watch_path] -%}
	{{svcname}}
{% endfor %}
{% endfor %}
```

With this template, you will get a plain list of the service names (one name per line) for every path in zk_watch_paths.

When using nginx, you can now build an URL list that will call respective upstream service (we will generate upstream list right after this):
```
{%- for zk_watch_path in ZK_TREE -%}
{% set env = zk_watch_path.split('/')[1] %}
{% for svcname in ZK_TREE[zk_watch_path] -%}
location /{{env}}/{{svcname}}/ {
	proxy_pass http://{{svcname}}-{{env}}/;
}
{% endfor %}
{% endfor %}
```

As you can see, I've parsed zk_watch_path to get the {{env}} variable (e.g: /test/service -> "test") and I used it as a suffix of "-{{env}}"
to identify the environment of the services. The resulting output will be:
```
location /dev/myservice1/ {
	proxy_pass http://myservice1-dev/;
}
location /dev/myservice2/ {
	proxy_pass http://myservice2-dev/;
}
...
```

And now, let's generate upstream section:
```
{%- for zk_watch_path in ZK_TREE -%}
{% set env = zk_watch_path.split('/')[1] %}
{% for svcname in ZK_TREE[zk_watch_path] -%}
upstream {{svcname}}-{{env}} {
	{%- for svcinstance in ZK_TREE[zk_watch_path][svcname] %}
	server {{ZK_TREE[searchbase][svcname][svcinstance]['payload']['listenAddress']}}:{{ZK_TREE[zk_watch_path][svcname][svcinstance]['payload']['listenPort']}};
	{%- endfor %}
}

{% endfor %}
{% endfor %}
```

Now there's 3 for loops that iterate over zk_watch_paths, service names and service instances respectively.
Let's say we have 2 services of the same type runnig and registered in the Zookeeper. This will result into:
```
upstream myservice1-dev {
	server 1.1.1.1:5555;
	server 1.1.1.2:5555;
}

upstream myservice2-dev {
	server 1.1.1.1:5556;
	server 1.1.1.2:5556;
}
...
```

Please note that variables "payload", "listenAddress" and "listenPort" are dropwizard-specific. But we know they're there so we can
safely use them. And not just from dropwizard. You can use any variable (if needed) as long as the node data is encoded in json.
You can experiment a bit and maybe print the whole ZK_TREE so you can see the raw data.
Remark: If you set any addtitional includepath_regex/excludepath_regex settings in the ini file, the resulting ZK_TREE may not contain
all the paths from zk_watch_paths.

And that's pretty much it regarding the templating.
See also comments in the templates for more info. And you can also see some jinja2 tutorial for advanced usage.

Further work
==================
This project is primarily used for dropwizard and it is tested the most with this use case. But the architecture of the program allows it to easily extend
the functionality to whatever is needed. Currently, the zkconfgen understands only one schema:
```
/<zk_watch_path>/<svc_name>/<instances_with_data>
```
so it expects to find instances (and most importantly - json encoded node data) on the second level of the Zookeeper tree under zk_watch_paths. If there exists other schema that cannot fit
(e.g. instance list right on the first level) or the instance node data is not in json format, then another config option will need to be added to cover it.
If such need arise, you can contact me. 
Or create a pull request :).

Jan

