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

echo ""
echo -e "\e[33mWelcome to this automated Snips My Flower satellite installer!\e[0m"
echo ""

echo -e "\e[33mPlease enter the name of this plant/flower\e[0m"
read -p 'Plant/flower name: ' plant
plant=${plant// /_}

echo ""
echo -e "\e[33mPlease enter the ip adress or the hostname of your main snips unit\e[0m"
read -p 'IP or hostname: ' ip

apt-get update
apt-get install -y git
apt-get install -y dirmngr
apt-get install -y python3-pip
bash -c  'echo "deb https://raspbian.snips.ai/$(lsb_release -cs) stable main" > /etc/apt/sources.list.d/snips.list'
apt-key adv --keyserver gpg.mozilla.org --recv-keys D4F50CDCA10A2849
apt-get update
apt-get install -y snips-audio-server
git clone https://github.com/respeaker/seeed-voicecard.git
cd seeed-voicecard
./install.sh
echo -e "\e[33m^^^^ No, don't reboot it, that's seeed respeaker installer telling you to, I will take care of that in a while ^^^^\e[0m"
cd ..

#rm /usr/bin/seeed-voicecard
#echo '#!/bin/bash
#amixer cset numid=3 1
#exit' | tee --append '/usr/bin/seeed-voicecard'
#
#rm /var/lib/alsa/asound.state
#ln -s /etc/voicecard/wm8960_asound.state /var/lib/alsa/asound.state
#rm /etc/asound.conf
#echo 'pcm.!default {
#  type asym
#   playback.pcm {
#     type plug
#     slave.pcm "hw:seeed2micvoicec"
#   }
#   capture.pcm {
#     type plug
#     slave.pcm "hw:seeed2micvoicec"
#   }
#}' | tee --append '/etc/asound.conf'
#
#alsactl restore

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
sed -i -e 's/\# bind = "default@mqtt"/bind = "'${plant}'@mqtt"/' /etc/snips.toml

systemctl is-active -q snipsMyFlower && systemctl stop snipsMyFlower

if [ ! -f /etc/systemd/system/snipsMyFlower.service ]; then
    cp snipsMyFlower.service /etc/systemd/system
fi

sed -i -e "s/snipsMyFlower[0-9\.abv_]*/snipsMyFlower_${VERSION}/" /etc/systemd/system/snipsMyFlower.service

rm /home/pi/snipsMyFlower_download.sh
rm action-snips-my-flower.py
rm config.default
rm i18n.json
rm I18n.py
rm plantsData.json
rm Plant.py
rm requirements.txt
rm setup.sh
mkdir logs

#grep -qF 'dtparam=i2c_arm=on' '/boot/config.txt' || echo 'dtparam=i2c_arm=on' | tee --append '/boot/config.txt'
grep -qF 'dtparam=i2c1_baudrate=30000' '/boot/config.txt' || echo 'dtparam=i2c1_baudrate=30000' | tee --append '/boot/config.txt'
#grep -qF 'dtparam=spi=on' '/boot/config.txt' || echo 'dtparam=spi=on' | tee --append '/boot/config.txt'
#grep -qF 'dtoverlay=seeed-2mic-voicecard' '/boot/config.txt' || echo 'dtoverlay=seeed-2mic-voicecard' | tee --append '/boot/config.txt'
#grep -qF 'i2c-dev' '/etc/modules' || echo 'i2c-dev' | tee --append '/etc/modules'
#grep -qF 'snd-soc-seeed-voicecard' '/etc/modules' || echo 'snd-soc-seeed-voicecard' | tee --append '/etc/modules'
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

chown -R pi /home/pi/snipsMyFlower_${VERSION}

systemctl daemon-reload
systemctl enable snipsMyFlower
systemctl restart snips-audio-server

echo -e "\e[33mRebooting...\e[0m"
sleep 3
reboot