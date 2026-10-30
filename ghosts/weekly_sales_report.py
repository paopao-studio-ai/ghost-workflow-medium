# weekly_sales_report.py  -- written 2012, python 2.7
# cron: 0 8 * * 1   (every Monday 08:00)
# Reads last week's orders export and emails a summary to the owner.
import csv, smtplib
from email.mime.text import MIMEText

total = 0.0
count = 0
for row in csv.DictReader(open('/data/exports/orders_last_week.csv')):
    total += float(row['amount'])
    count += 1

body = "Orders: %d\nRevenue: %.2f" % (count, total)
msg = MIMEText(body)
msg['Subject'] = 'Weekly sales report'
msg['From'] = 'robot@example.com'
msg['To'] = 'owner@example.com'
s = smtplib.SMTP('localhost')
s.sendmail(msg['From'], [msg['To']], msg.as_string())
s.quit()
