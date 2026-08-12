from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, localcontext

MONEY_QUANTUM = Decimal("0.01")
INTERMEDIATE_QUANTUM = Decimal("0.0001")
PERCENT = Decimal("100")
ZERO = Decimal("0")


def as_decimal(value):
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def quantize_money(value):
    return as_decimal(value).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def quantize_intermediate(value):
    return as_decimal(value).quantize(
        INTERMEDIATE_QUANTUM,
        rounding=ROUND_HALF_UP,
    )


@dataclass(frozen=True)
class LineInput:
    quantity: Decimal
    unit_rate: Decimal
    is_taxable: bool
    tax_rate: Decimal = ZERO


@dataclass(frozen=True)
class LineResult:
    line_subtotal: Decimal
    allocated_discount: Decimal
    taxable_amount: Decimal
    tax_amount: Decimal
    line_total: Decimal


@dataclass(frozen=True)
class EstimateCalculation:
    lines: tuple[LineResult, ...]
    subtotal: Decimal
    discount_amount: Decimal
    tax_amount: Decimal
    total: Decimal
    deposit_required: Decimal


def _document_amount(*, amount_type, value, base, field_name):
    value = as_decimal(value)
    if value < ZERO:
        raise ValueError(f"{field_name} cannot be negative.")
    if amount_type == "none":
        return ZERO
    if amount_type == "percentage":
        if value > PERCENT:
            raise ValueError(f"{field_name} percentage cannot exceed 100.")
        return quantize_money(base * value / PERCENT)
    if amount_type == "fixed":
        amount = quantize_money(value)
        if amount > base:
            raise ValueError(f"{field_name} cannot exceed the document total.")
        return amount
    raise ValueError(f"Unknown {field_name} type.")


def _allocate_discount(subtotals, discount_amount, subtotal):
    if not subtotals or discount_amount == ZERO:
        return [ZERO for _ in subtotals]
    if subtotal == ZERO:
        return [ZERO for _ in subtotals]

    allocations = []
    remaining = discount_amount
    with localcontext() as context:
        context.prec = 28
        for index, line_subtotal in enumerate(subtotals):
            if index == len(subtotals) - 1:
                allocation = min(remaining, line_subtotal)
            else:
                allocation = quantize_money(discount_amount * line_subtotal / subtotal)
                allocation = min(allocation, remaining, line_subtotal)
            allocations.append(allocation)
            remaining -= allocation
    if remaining:
        for index in range(len(allocations) - 2, -1, -1):
            capacity = subtotals[index] - allocations[index]
            adjustment = min(remaining, capacity)
            allocations[index] += adjustment
            remaining -= adjustment
            if remaining == ZERO:
                break
    if remaining != ZERO:
        raise ValueError("Discount allocation did not reconcile.")
    return allocations


def calculate_estimate(
    lines,
    *,
    discount_type="none",
    discount_value=ZERO,
    deposit_type="none",
    deposit_value=ZERO,
):
    line_inputs = tuple(lines)
    raw_subtotals = []
    for line in line_inputs:
        quantity = as_decimal(line.quantity)
        unit_rate = as_decimal(line.unit_rate)
        tax_rate = as_decimal(line.tax_rate)
        if quantity <= ZERO:
            raise ValueError("Line quantity must be greater than zero.")
        if unit_rate < ZERO:
            raise ValueError("Line rate cannot be negative.")
        if tax_rate < ZERO or tax_rate > PERCENT:
            raise ValueError("Tax rate must be between 0 and 100.")
        raw_subtotals.append(quantize_intermediate(quantity * unit_rate))

    money_subtotals = [quantize_money(value) for value in raw_subtotals]
    subtotal = quantize_money(sum(money_subtotals, ZERO))
    discount_amount = _document_amount(
        amount_type=discount_type,
        value=discount_value,
        base=subtotal,
        field_name="discount",
    )
    allocations = _allocate_discount(
        money_subtotals,
        discount_amount,
        subtotal,
    )

    results = []
    for line, line_subtotal, allocated_discount in zip(
        line_inputs,
        money_subtotals,
        allocations,
        strict=True,
    ):
        discounted_amount = line_subtotal - allocated_discount
        taxable_amount = discounted_amount if line.is_taxable else ZERO
        tax_amount = (
            quantize_money(taxable_amount * as_decimal(line.tax_rate) / PERCENT)
            if line.is_taxable
            else ZERO
        )
        results.append(
            LineResult(
                line_subtotal=line_subtotal,
                allocated_discount=allocated_discount,
                taxable_amount=taxable_amount,
                tax_amount=tax_amount,
                line_total=discounted_amount + tax_amount,
            )
        )

    tax_amount = quantize_money(sum((line.tax_amount for line in results), ZERO))
    total = subtotal - discount_amount + tax_amount
    deposit_required = _document_amount(
        amount_type=deposit_type,
        value=deposit_value,
        base=total,
        field_name="deposit",
    )
    return EstimateCalculation(
        lines=tuple(results),
        subtotal=subtotal,
        discount_amount=discount_amount,
        tax_amount=tax_amount,
        total=total,
        deposit_required=deposit_required,
    )


def to_minor_units(value, *, exponent=2):
    value = as_decimal(value)
    if exponent < 0 or exponent > 4:
        raise ValueError("Currency exponent must be between 0 and 4.")
    quantum = Decimal(1).scaleb(-exponent)
    quantized = value.quantize(quantum, rounding=ROUND_HALF_UP)
    return int(quantized.scaleb(exponent))
