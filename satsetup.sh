#!/bin/bash
VENV=venv

if [ "$EUID" -ne 0 ]
  then echo "Please run with sudo"
  exit
fi

echo "dtparam=i2c1_baudrate=30000" >> /boot/config.txt

pip3 install virtualenv
mkdir logs

if [ ! -d "$VENV" ]
then
    PYTHON=`which python3`

    if [ ! -f $PYTHON ]
    then
        echo "Please install Python 3"
        exit
    fi
    virtualenv -p $PYTHON $VENV
fi

. $VENV/bin/activate
pip3 install -r sat_requirements.txt