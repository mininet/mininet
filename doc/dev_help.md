# Developer instructions helper

For easier development a IDE could be used.
The following instructions are for Pycharm from IDEA but could be applied to others.

### Running the code

To run the code the python execution should load from Mininet-WiFi code from the mininet folder in the project and not the installed version.
To force this, one option is uninstall any instaled versions using pip:
> pip uninstall mininet

Then in a shell with superuser permission make sure that the python path is the root of the project
> export PYTHONPATH=....(dir root of mininet)

At last you can run any example simply by doing in the terminal:
> python file.py


### Running code using Pycharm

To make it easier run the code in Pycharm (or other IDEs), add the script localized in utils/python_sudo.sh as a Python Interpreter.

If you get the no tty for authentication when trying to run an example, you need to make our script not ask for password to run as superuser. 
To do that, edit sudoers or add a new entry (/etc/sudoers.d/mininet) with:
> your_user ALL = (root) NOPASSWD: /path/to/utils/python_sudo_helper.sh

After this you should be able to run any scripts in the IDE using utils/python_sudo.sh as a Python Interpreter.

The downside of this is you will not be able to kill the process with Pycharm, if you need to kill it jump to the terminal and find it using _ps_ and use _kill_.