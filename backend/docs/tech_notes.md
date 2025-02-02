Enshittification Metrics Technical Notes:

# PRODUCTION ENVIRONMENT:

## em02 (DigitalOcean droplet):
#### Build droplet on DigitalOcean
- SF region / SFO3
- Ubuntu 24.04
- basic
- regular CPU
- $6/month: 1GB; 1 CPU; 25GB SSD; 1000GB transfer
- use "one_drop_01" ssh key (created w/ PuTTY Key Generator)
- metrics monitoring and alerting enabled (*** how to use this?)
- IPv6 enabled
- hostname: em02
- ip: 143.198.73.217
- linked to cloud firewall "Bristol-One"
#### create non-root user
- ssh -i priv_key root@143.198.73.217
-- Note: Can WinSCP w/ one_drop_01 with cert.ppk and passphrase; Can powershell ssh -i with openssh_format cert and passphrase; Unable to PuTTY... (***)
- adduser bsea # Byron Seabringer; bristol4@enshittificationmetrics.com; password in BW
- usermod -aG sudo bsea # to enable sudo
- rsync --archive --chown=bsea:bsea ~/.ssh /home/bsea # to copy private key for ssh
- exit
#### setup software
- ssh -i priv_key bsea@143.198.73.217
- sudo apt update
- sudo apt upgrade -y
- sudo apt install apache2 -y
- TEST Apache: http://143.198.73.217 over internet returns Apache page!
- sudo apt install libapache2-mod-wsgi-py3 -y
- python3 --version # reports Python 3.12.3
- sudo apt install pipenv -y
#### copy in code
- WinSCP as root:
-- make /home/bsea/em
-- copy in backend .py scripts, .env, Pipfile
-- make /var/www/em
-- copy website flask files in
-- tweak .env to set different/unique FLASK_SECRET_KEY (excluded from git version control by .gitignore so each instance has own .env)
-- delete out dev-only routes for soft launch (*** remove these lines once dev code locks down and has user logins)
--- from /var/www/em/app/routes.py
--- from /var/www/em/app/templates/base.html
-- tweak /var/www/em/instance/em.db to give group write rights (to write to www DB from backend) (*** write this line as chmod cmd)
#### config Apache http and https (and SSL cert and cert renewal)
- create / configure em.conf, for http, w/ ServerName, ServerAlias, and, ServerAdmin; pointing at /var/www/em/index.html
- sudo a2ensite em.conf
- sudo a2dissite 000-default.conf
- sudo systemctl reload apache2
- TEST http://www.enshittificationmetrics.com over internet returns http port 80 em/index.html!
- setup https Let's Encrypt and test https lock and auto renewal (https://www.digitalocean.com/community/tutorials/how-to-secure-apache-with-let-s-encrypt-on-ubuntu)
-- sudo apt install certbot python3-certbot-apache
-- sudo apache2ctl configtest
-- sudo systemctl restart apache2
-- sudo ufw status # not enabled - using cloud firewall
-- sudo certbot --apache # entered bristol4@enshittificationmetrics.com
-- sudo systemctl status certbot.timer
-- sudo certbot renew --dry-run
- sudo systemctl reload apache2
- TEST https://www.enshittificationmetrics.com over internet returns https port 443 em/index.html!
- setup em.conf to redirect to https
- Add "ServerName enshittificationmetrics.com" to /etc/apache2/apache2.conf (eliminates warning on Apache start)
#### config group and file permissions
- sudo groupadd www-rwx # create group
- sudo usermod -aG www-rwx root # add root to group
- sudo usermod -aG www-rwx www-data # add www-data to group
- sudo usermod -aG www-rwx bsea # add bsea to group (to write to www DB from backend)
- getent group www-rwx # to see who is in the group
- sudo chown -R :www-rwx /var/www/em # set rights for em folder and down
- sudo chmod -R 2775 /var/www/em # set rights for em folder and down (lead 2, Set GUID, ensures that the copied or created files inherit the directory's group ownership, not the user's primary group)
- on /home/bsea/ set x for others (Directory Traversal Permissions), so www-data can access; all rest already set (*** write this line as chmod cmd)
- sudo chown -R bsea: /home/bsea/em # set owner in home, as copied in via root via WinSCP
#### setup Python virtual environments
- cd /home/bsea/em
- pipenv install
- cd /var/www/em
- sudo pipenv install
- pipenv --venv # (run in /var/www/em) returns: /home/bsea/.local/share/virtualenvs/em-eHcyI4u8
-- Note this is "old" path for now backend which doesn't use wsgi: /home/bsea/.local/share/virtualenvs/em-skG7guJD (***)
- sudo chown -R :www-rwx /home/bsea/.local/share/virtualenvs/em-eHcyI4u8/bin/activate_this.py # set rights for activate_this.py (is this needed?)
- sudo chmod -R 2775 /home/bsea/.local/share/virtualenvs/em-eHcyI4u8/bin/activate_this.py # set rights for activate_this.py (is this needed?)
#### configure WSGI
- copy in /var/www/em/middleapp.wsgi
-- set sys.path.insert
-- set activate_this path (from --venv above)
-- set em as from import
- setup em-le-ssl.conf to point to wsgi/flask site
- sudo systemctl restart apache2 # restart Apache so changes can take effect
- TEST: https://www.enshittificationmetrics.com over internet returns needed website!
- Note: logs here: /var/log/apache2/access.log and error.log, and /var/www/em/log.log
#### install and config fail2ban
- sudo apt update
- sudo apt install fail2ban
- sudo apt upgrade fail2ban
- sudo systemctl enable fail2ban
- sudo systemctl start fail2ban
- sudo cp /etc/fail2ban/jail.conf /etc/fail2ban/jail.local
- edit jail.local and enable: apache-auth, apache-badbots, and apache-nohome (sshd already enabled)
- sudo fail2ban-client status # returns: Jail list:   apache-auth, apache-badbots, apache-nohome, sshd
- Note: logs here: /var/log/fail2ban.log
#### setup "bsea" cron jobs to backend
- set crontab -e to: 20 21 * * * /usr/bin/python3 /home/bsea/em/utilities/cronntfy.py
- set crontab -e to: 20 * * * * cd /home/bsea/em/ && pipenv run python3 slashdot_scrape.py >> /home/bsea/em/scrape.log 2>&1
- set crontab -e to: 0 10 * * * cd /home/bsea/em/ && pipenv run python3 populate_blanks.py >> /home/bsea/em/scrape.log 2>&1
- set crontab -e to: 0 12 * * * /usr/bin/python3 /home/bsea/em/utilities/rotate_db_backup.py
- set crontab -e to: 50 1-23/2 * * * /usr/bin/python3 /home/bsea/em/utilities/copy_github_to_local.py
- sudo cp /home/bsea/em/utilities/enshittification-metrics /etc/logrotate.d/enshittification-metrics
#### setup "root" cron jobs to backend
- None (yet)
#### setup GitHub code pull (replaces "copy in code" above)
- mkdir /home/bsea/github
- cd /home/bsea/github
- git init # only first time
- git branch -M main # only first time
- git remote add origin https://github.com/EnshittificationMetrics/EnshittificationMetrics.git
- git config --global user.email "bristol4@enshittificationmetrics.com"
- git config --global user.name "bristol4@enshittificationmetrics.com"
- git status # test to see if working
- git config --list # to see git config
- sudo apt update
- sudo apt install gh # GitHub CLI
- gh auth login # minimum required scopes are 'repo', 'read:org', 'workflow'
-- HTTPS
-- Y
-- paste "Access EM repo; gh auth login" personal access token (classic)
#### user management
- Note: Initially, with fresh DB, would have to create "Guest" in web UI, then set to role=guest per below, also create and set an admin
- cd www pipefile location
- pipenv shell
- flask shell
- query = sa.select(User)
- users = db.session.scalars(query)
- for u in users:
- ... print(u.id, u.username, u.role)
- z = db.session.get(User, 2) # 2 is example, use listed index values
- z.role = 'disabled' # guest, regular, administrator, or, disabled
- db.session.commit()
