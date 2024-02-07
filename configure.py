#!/usr/bin/env python3
import subprocess
import re
from pathlib import Path
import ipaddress
import json

class SambaShareConfigurator:
  def __init__(self):

    print("QEMU Samba Shared Configurator")
    print("==============================\n")

    self.iface = self.get_iface()
    self.current_dir = Path(__file__).parent.resolve()

    self.cidr = self.get_cidr()

    if not self.cidr:
      print("Unable to get CIDR for interface {}".format(self.iface))
      exit(1)

    self.script_dir = Path(self.current_dir, "scripts")
    self.config_dir = Path(self.current_dir, "configs")

    self.script_dir = Path(input(f"Scripts dir absolute path [{self.script_dir}]: ") or self.script_dir)
    self.config_dir = Path(input(f"Configs dir absolute path [{self.config_dir}]: ") or self.config_dir)
    self.qemu_hook_config = self.get_qemu_hook_config()

    print(f"\nSubnet                    : {self.cidr}")
    print(f"Docker network name       : docker-{self.iface}")

    self.network_scripts()
    self.create_vm_config()
    self.edit_qemu_hook_config()

  def get_iface(self):
    suggested_iface = "virbr0"
    return input(f"Virtual Bridge interface [{suggested_iface}]: ") or suggested_iface

  def get_cidr(self):
    out = subprocess.run(["ip", "-4", "a", "show", "dev", self.iface], capture_output=True, text=True)
    if out.returncode == 0:
      match = re.search(r"inet (\d+\.\d+\.\d+\.\d+/\d+)", out.stdout)
      if match:
        network = ipaddress.ip_network(match.group(1), strict=False)
        return f"{network.network_address}/{network.prefixlen}"

  def network_scripts(self):
    paths = []
    Path.mkdir(self.script_dir, parents=True, exist_ok=True)
    for action in ["create", "remove"]:
      script = Path(self.script_dir, f"{action}-docker-{self.iface}.sh")
      with open(script, "w") as f:
        if action == "create":
          f.write(
            (
              "#!/bin/bash\n"
              f"docker network create --driver=macvlan --subnet={self.cidr} -o parent={self.iface} docker-{self.iface}\n"
            )
          )
        else:
          f.write(
            (
              "#!/bin/bash\n"
              f"docker network rm docker-{self.iface}\n"
            )
          )
      script.chmod(0o775)
      paths.append(script)
    self.create_script_path, self.remove_script_path = paths

  def get_vm_list(self):
    out = subprocess.run(["virsh", "list", "--all", "--name"], capture_output=True, text=True)
    if out.returncode == 0:
      vms = []
      for line in out.stdout.splitlines():
        if line:
          vms.append(line)
      return vms
  
  def valid_config_name(self, name):
    return re.match(r"^[a-zA-Z0-9_-]+$", name)
  
  def get_other_config_ips(self):
    ips = []
    for config in Path(self.config_dir).glob("*/*.yml"):
      with config.open() as f:
        config_yml = f.read()
      match = re.search(r"ipv4_address: (\d+\.\d+\.\d+\.\d+)", config_yml)
      if match:
        ips.append(match.group(1))
    return ips
  
  def get_valid_ip(self):
    other_ips = self.get_other_config_ips()
    other_ips.append(self.cidr.split("/")[0])
    suggested_ip = ""

    first = True
    for ip in ipaddress.IPv4Network(self.cidr, strict=False):
      if str(ip) not in other_ips:
        if not first:
          suggested_ip = str(ip)
          break
        first = False

    while True:
      ip = input(f"IP address [{suggested_ip}]: ") or suggested_ip
      if re.match(r"^\d+\.\d+\.\d+\.\d+$", ip):
        return ip
      else:
        print("Invalid IP address")

  def get_qemu_hook_config(self):
    print("\nQEMU hook configuration, required\n")
    print(" https://github.com/jfhack/qemu-hook\n")
    suggested_path = "../qemu-hook/config.json"
    if not Path(suggested_path).exists():
      suggested_path = ""
    while True:
      qemu_hook = input(f"QEMU hook config.json path [{suggested_path}]: ") or suggested_path
      if qemu_hook:
        qemu_hook = Path(qemu_hook)
        if qemu_hook.exists():
          return qemu_hook
        else:
          print("File not found")

  def edit_qemu_hook_config(self):
    with self.qemu_hook_config.open() as f:
      config = json.load(f)

    commands = dict(
      start = [
        [str(self.create_script_path)],
        ["docker", "compose", "-f", str(self.docker_compose_path), "up", "-d"]
      ],
      stopped = [
        ["docker", "compose", "-f", str(self.docker_compose_path), "down", "-v"],
        [str(self.remove_script_path)]
      ]
    )
    
    if self.vm_name not in config:
      config[self.vm_name] = {}
    
    if "start" not in config[self.vm_name]:
      config[self.vm_name]["start"] = []
    
    if "stopped" not in config[self.vm_name]:
      config[self.vm_name]["stopped"] = []
    
    for action in commands.keys():
      if len(config[self.vm_name][action]) > 0:
        print(f"\nQEMU hook already contains {action} commands for this VM:")
        for cmd in config[self.vm_name][action]:
          print(f"  {' '.join(cmd)}")
        overwrite = input("\nOverwrite? [y/N]: ").lower() == "y"
        if not overwrite:
          for cmd in commands[action]:
            if cmd not in config[self.vm_name][action]:
              config[self.vm_name][action].append(cmd)
        else:
          config[self.vm_name][action] = commands[action]
      else:
        config[self.vm_name][action] = commands[action]
    with self.qemu_hook_config.open("w") as f:
      json.dump(config, f, indent=2)
    print("\nQEMU hook configuration updated")

  def create_vm_config(self):
    vm_list = self.get_vm_list()
    vm_name = None
    if vm_list:
      print("\nSelect VM to create a samba configuration:")
      print(f"0. Not listed VM (input VM name)")
      for i, vm in enumerate(vm_list):
        print(f"{i+1}. {vm}")
      suggested_vm_index = ""
      if len(vm_list) == 1:
        suggested_vm_index = "1"
      while True:
        try:
          vm_index = int(input(f"VM index [{suggested_vm_index}]: ") or suggested_vm_index)
          if 0 <= vm_index <= len(vm_list):
            break
          else:
            print("Invalid VM index")
        except ValueError:
          print("Invalid VM index")
      if vm_index > 0:
        vm_name = vm_list[vm_index-1]
        print(f"\nSelected VM: {vm_name}")
    else:
      print("No VM found")
    
    if not vm_name:
      vm_name = input("VM name: ")
      while not vm_name:
        vm_name = input("VM name: ")
    self.vm_name = vm_name
    print("Creating VM config...\n")
    self.config_dir.mkdir(parents=True, exist_ok=True)
    print("Input config name (alphanumeric, underscore and dash only)")
    print("Used in docker-compose.yml, e.g. with fermi the container will be samba-fermi")
    config_name = ""
    if self.valid_config_name(vm_name):
      config_name = vm_name
    config_name = input(f"Config name [{config_name}]: ") or config_name

    while not self.valid_config_name(config_name):
      print("Invalid config name")
      config_name = input("Config name: ")
    self.config_name = config_name

    with Path(self.current_dir, "template.yml").open() as f:
      config_yml = f.read()

    config_ip = self.get_valid_ip()
    config_shared_dir = "./shared"
    config_shared_dir = Path(input(f"Shared directory path [{config_shared_dir}]: ") or config_shared_dir)
    
    config_yml = config_yml.replace("{{config_name}}", self.config_name)
    config_yml = config_yml.replace("{{docker_iface}}", f"docker-{self.iface}")
    config_yml = config_yml.replace("{{config_ip}}", config_ip)
    config_yml = config_yml.replace("{{config_shared_dir}}", str(config_shared_dir))

    Path(self.config_dir, self.config_name).mkdir(parents=True, exist_ok=True)

    self.docker_compose_path = Path(self.config_dir, self.config_name, "docker-compose.yml")

    with self.docker_compose_path.open("w") as f:
      f.write(config_yml)
    print("\nConfig created successfully")
    print(f"Config path: {self.docker_compose_path.parent}")
    

def main():
  SambaShareConfigurator()

if __name__ == "__main__":
  main()
