PMR: The Process Maps Restarter
===

Requirements
---

 * Python 3
 * systemd
 * DNF (soon)

Installation on Fedora, RHEL, or CentOS
---

    sudo yum install -y python3-pip python3-dnf git
    sudo pip-python3 install git+git://github.com/pantheon-systems/pmr.git@master

Doing a dry run
---

    sudo pmr --dry-run --verbose

Restarting matched services
---

    sudo pmr

Default /etc/pmr.ini
---

    [unit]
    *.service = true

    [cmdline]
    * = true

Installation (for development) from a clone
---

    sudo python3 setup.py install
