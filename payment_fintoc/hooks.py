from odoo import SUPERUSER_ID, api


def post_init_hook(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['payment.provider'].sudo().search([
        ('code', '=', 'fintoc')
    ])._fintoc_ensure_accounting_setup()
