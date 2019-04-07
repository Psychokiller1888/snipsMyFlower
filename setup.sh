#!/usr/bin/env bash -e

VENV=venv

if [ ! -e config.ini ]; then
    cp config.default config.ini
    chmod a+w config.ini
fi

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

pip3 install -r requirements.txt