PMR: The Process Maps Restarter
===

Requirements
---

 * Python 3
 * systemd

Installation on Fedora, RHEL, or CentOS
---

    sudo yum install -y python3-pip git
    sudo pip-python3 install git+git://github.com/pantheon-systems/pmr.git

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

Building, testing, and publishing
---

    sudo pip-python3 install wheel
    python3 setup.py sdist
    python3 setup.py bdist_wheel
    python3 setup.py sdist upload [-r test]
    python3 setup.py bdist_wheel upload [-r test]
    pip-python3 install [-i https://testpypi.python.org/pypi] pmr
