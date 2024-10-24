## odoo/tools/spdt_cart_maint.py
from odoo.http import request

def clear_cart():
    ## SAME CODE AS wwebsite_sales MAIN CONTROLLER'S /shop/cart/clear
    order = request.website.sale_get_order()
    for line in order.order_line:
        line.unlink()