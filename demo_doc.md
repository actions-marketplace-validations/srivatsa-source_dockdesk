# Refund Policy

Refunds are processed based on user role and refund amount.

## Refund Amount Limit
Only admins are allowed to process refunds over $100.

## User Role Restriction
Non-admin users cannot process refunds above $100.

## Error Handling
If a non-admin user attempts to process a refund over $100, a PermissionError is raised.

## Refund Processing
If the refund amount is $100 or less, or if the user is an admin, the refund is processed and a confirmation message is provided.