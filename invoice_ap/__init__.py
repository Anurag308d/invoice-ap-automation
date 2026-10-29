"""invoice_ap: invoice-to-pay (accounts payable) automation on a reproducible synthetic dataset.

Pipeline: synthetic ERP world + rendered invoice documents (generator) -> intake and field
extraction -> validation, duplicate detection and three-way matching -> exception routing ->
approvals -> payment readiness (engine) -> evaluation against a rule-derived ground truth.
"""
__version__ = "0.1.0"
