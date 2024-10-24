#!/bin/zsh

# given a script parm, use it as default port, otherwise :8069
if [[ -z $1 ]];
then 
    python odoo-bin -d odoo-prod1 --addons-path addons,odoo/addons
else
    python odoo-bin  -p $1 -d odoo-prod1 --addons-path addons,odoo/addons
fi
