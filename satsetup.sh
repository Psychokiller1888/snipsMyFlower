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

echo "Welcome in this automated Snips My Flower satellite installer!"
echo ""

echo "Please enter the name of this plant/flower"
read -p 'Plant/flower name: ' plant

plant=${plant// /_}

echo "Please enter the ip adress or the hostname of your main snips unit"
read -p 'IP or hostname: ' ip

apt-get update
apt-get install -y git
apt-get install -y dirmngr
bash -c  'echo "deb https://raspbian.snips.ai/$(lsb_release -cs) stable main" > /etc/apt/sources.list.d/snips.list'
apt-key adv --keyserver gpg.mozilla.org --recv-keys D4F50CDCA10A2849
apt-get update
apt-get install -y snips-audio-server
git clone https://github.com/respeaker/seeed-voicecard.git
cd seeed-voicecard
./install.sh
echo "^^^^ No, don't reboot it, that's seeed respeaker installer telling you too, I will take care of that in a while ^^^^"
cd ..

rm /etc/voicecard/asound_2mic.conf

echo 'pcm.!default {
  type asym
   playback.pcm {
     type plug
     slave.pcm "hw:seeed2micvoicec"
   }
   capture.pcm {
     type plug
     slave.pcm "hw:seeed2micvoicec"
   }
}' | tee --append '/etc/voicecard/asound_2mic.conf'

sed -i -e 's/\# mqtt = "localhost:1883"/mqtt = "'${ip}':1883"/' /etc/snips.toml
sed -i -e 's/\# bind = \["default@mqtt"\]/bind = \["'${plant}'@mqtt"\]/' /etc/snips.toml

systemctl is-active -q snipsMyFlower && systemctl stop snipsMyFlower

if [ ! -f /etc/systemd/system/snipsMyFlower.service ]; then
    cp snipsMyFlower.service /etc/systemd/system
fi

sed -i -e "s/snipsMyFlower[0-9\.av_]*/snipsMyFlower_${VERSION}/" /etc/systemd/system/snipsMyFlower.service

rm /home/pi/snipsMyFlower_download.sh
rm action-snips-my-flower.py
rm config.default
rm i18n.json
rm I18n.py
rm plantsData.json
rm requirements.txt
rm setup.sh
mkdir logs

grep -qF 'dtparam=i2c1_baudrate=30000' '/boot/config.txt' || echo 'dtparam=i2c1_baudrate=30000' | tee --append '/boot/config.txt'

pip3 install virtualenv

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
systemctl restart snips-audio-server

echo "Rebooting..."
sleep 3
reboot