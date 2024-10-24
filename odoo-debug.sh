#!/bin/zsh

python3 -m ptvsd --host localhost --port 5678 odoo-bin -d odoo-prod1 --addons-path addons,odoo/addons --dev=reload,werkzeug,xml --log-level=debug
