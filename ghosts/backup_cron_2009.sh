#!/bin/bash
# crontab -e   (added by "the intern", March 2009)
#   0 3 * * * /home/shop/bin/nightly_backup.sh >> /var/log/nightly_backup.log 2>&1
#
# Nightly backup of the shop database and invoices folder.
# DO NOT DELETE - nobody knows how to restore without it.

DATE=$(date +%Y%m%d)
mysqldump -u shop -p"$DB_PASS" shopdb > /tmp/shopdb_$DATE.sql
tar czf /backup/shop_$DATE.tar.gz /tmp/shopdb_$DATE.sql /home/shop/invoices
scp /backup/shop_$DATE.tar.gz backup@192.168.1.20:/mnt/nas/shop/
find /backup -name "shop_*.tar.gz" -mtime +14 -delete
echo "Backup $DATE done" | mail -s "nightly backup ok" boss@example.com
