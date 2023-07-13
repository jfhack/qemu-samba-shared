# QEMU Samba Shared
This is a simple Python script that allows you to configure a shared directory for QEMU using Samba through Docker

It requires [qemu-hook](https://github.com/jfhack/qemu-hook) to be installed, as well as the Docker Compose plugin

# Configuration

To start, run the main script:

```sh
./configure.py
```

It will ask you for the following parameters:

 Parameter | Description | Default
 -- | -- | --
**Virtual Bridge Interface** | This is the virtual interface that will be used to link the containers | `virbr0`
**Scripts Directory** | An absolute path where the scripts to create and remove the docker interfaces will be stored | `scripts/` <br> _(absolute path)_
**Configs Directory** | An absolute path where the configurations will be saved. These configurations are the docker compose files containing the Samba configuration. This is relevant in case the volumes are relative to the YAML file location | `configs/` <br> _(absolute path)_
**QEMU Hook Configuration File** | This is the `config.json` file path from [qemu-hook](https://github.com/jfhack/qemu-hook). This file is responsible for creating and destroying the network interfaces and for bringing up and taking down the container | `../qemu-hook/config.json` <br> _(if it exists)_
**VM Domain Name** | The VM domain name. The script will offer you a list of the installed ones. You can select them through their one-based index. Choosing zero means the name will be asked as text | 
**Config Name** | This is a custom name for the configuration. It will be used as a directory and part of the container name, so keep them unique to allow running the containers in parallel if the configured VMs are operating simultaneously | _(selected VM domain)_
**IP Address** | This is the container IP. It needs to be a subnet of the libvirt interface, and will be used to access the shared directory. For example, `192.168.122.3` could be accessed from Windows as `\\192.168.122.3\shared` | _(an IP that is neither the first nor previously used in configurations)_
**Shared Directory** | This is the local directory that will be mounted as `shared` inside the container and will be accessible via Samba | `./shared`

After the configuration is complete, it's recommended to run `docker pull ghcr.io/jfhack/samba:latest`. This will download the Docker image in advance, saving time during the initial launch
