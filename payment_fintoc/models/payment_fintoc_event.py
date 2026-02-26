from odoo import fields, models


class PaymentFintocEvent(models.Model):
    _name = 'payment.fintoc.event'
    _description = 'Fintoc Webhook Event'
    _order = 'id desc'

    event_id = fields.Char(required=True, index=True)
    provider_id = fields.Many2one(
        comodel_name='payment.provider',
        required=True,
        ondelete='cascade',
    )
    event_type = fields.Char(required=True)
    transaction_id = fields.Many2one(
        comodel_name='payment.transaction',
        ondelete='set null',
    )
    payload = fields.Text()
    state = fields.Selection(
        selection=[
            ('received', 'Received'),
            ('processed', 'Processed'),
            ('error', 'Error'),
        ],
        default='received',
        required=True,
    )
    error_message = fields.Char()
    processed_date = fields.Datetime()

    _sql_constraints = [
        ('payment_fintoc_event_unique', 'unique(event_id)', 'Webhook event already processed.'),
    ]
