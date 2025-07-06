echo "Cron job started at $(date)" >> /tmp/cron.log
cd /home/aifeier/local-dev/freq_conf
source /home/aifeier/.bashrc
proxy
source /home/aifeier/miniconda3/bin/activate base
python tools/self_time_50bilile.py >> /tmp/cron.log 2>&1
./ossutil cp /home/aifeier/local-dev/freq_conf/tools/../gen_pairs/50bili.json  oss://freq/gen_pairs/50bili.json -f
