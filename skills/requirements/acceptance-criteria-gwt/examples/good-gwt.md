# Good GWT Example

**Story:** As a customer, I want to apply a discount code at checkout so that I save money.

## Scenario 1: Valid discount code applied
- **Given** the customer has items totaling $100 in their cart
- **And** a valid discount code "SAVE20" exists for 20% off
- **When** the customer enters "SAVE20" and clicks Apply
- **Then** the order total is reduced to $80
- **And** the discount is shown as a line item "-$20.00"

## Scenario 2: Expired discount code
- **Given** the customer has items in their cart
- **And** the discount code "OLD10" expired yesterday
- **When** the customer enters "OLD10" and clicks Apply
- **Then** an error message states "This code has expired"
- **And** the order total remains unchanged

## Scenario 3: Minimum spend not met
- **Given** the customer has items totaling $15 in their cart
- **And** a valid code "SAVE20" requires minimum spend of $50
- **When** the customer enters "SAVE20" and clicks Apply
- **Then** an error message states "Minimum spend of $50 required"

## Why these are good
- Each tests ONE behavior
- Given establishes specific, concrete context
- When is a single user action
- Then is observable and verifiable
- No implementation details
