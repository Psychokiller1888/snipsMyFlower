#!/bin/bash
VENV=venv

if [ "$EUID" -ne 0 ]
  then echo "Please run with sudo"
  exit
fi

if [ -z "$1" ]; then
    echo "No version supplied"
    exit
else
    VERSION=$1
fi

USER=$(logname)
systemctl is-active -q snipsMyFlower && systemctl stop snipsMyFlower

if [ ! -f /etc/systemd/system/snipsMyFlower.service ]; then
    cp snipsMyFlower.service /etc/systemd/system
fi

sed -i -e "s/snipsMyFlower[0-9\.v_]*/snipsMyFlower_${VERSION}/" /etc/systemd/system/snipsMyFlower.service

rm action-snips-my-flower.py
rm config.default
rm i18n.json
rm i18n.py
rm plantsData.json
rm requirements.txt
rm setup.sh

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

systemctl daemon-reload
systemctl enable snipsMyFlower
systemctl start snipsMyFlower