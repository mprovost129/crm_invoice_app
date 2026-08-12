from decimal import Decimal

import pytest

from estimates.calculations import LineInput, calculate_estimate, to_minor_units


def test_percentage_discount_is_allocated_before_tax_and_deposit():
    result = calculate_estimate(
        (
            LineInput(Decimal("2"), Decimal("50"), True, Decimal("10")),
            LineInput(Decimal("1"), Decimal("100"), False),
        ),
        discount_type="percentage",
        discount_value=Decimal("10"),
        deposit_type="percentage",
        deposit_value=Decimal("25"),
    )

    assert result.subtotal == Decimal("200.00")
    assert result.discount_amount == Decimal("20.00")
    assert [line.allocated_discount for line in result.lines] == [
        Decimal("10.00"),
        Decimal("10.00"),
    ]
    assert result.lines[0].taxable_amount == Decimal("90.00")
    assert result.tax_amount == Decimal("9.00")
    assert result.total == Decimal("189.00")
    assert result.deposit_required == Decimal("47.25")


def test_fixed_discount_and_deposit_reconcile_to_document_totals():
    result = calculate_estimate(
        (
            LineInput(Decimal("1"), Decimal("100"), True, Decimal("10")),
            LineInput(Decimal("1"), Decimal("100"), False),
        ),
        discount_type="fixed",
        discount_value=Decimal("30"),
        deposit_type="fixed",
        deposit_value=Decimal("50"),
    )

    assert result.discount_amount == Decimal("30.00")
    assert result.tax_amount == Decimal("8.50")
    assert result.total == Decimal("178.50")
    assert result.deposit_required == Decimal("50.00")
    assert sum((line.line_total for line in result.lines), Decimal("0")) == result.total


def test_money_rounding_is_decimal_half_up_and_never_uses_float_math():
    result = calculate_estimate((LineInput(Decimal("1.005"), Decimal("1"), False),))

    assert result.subtotal == Decimal("1.01")
    assert to_minor_units(Decimal("1.005")) == 101


@pytest.mark.parametrize(
    ("line", "kwargs"),
    (
        (LineInput(Decimal("0"), Decimal("1"), False), {}),
        (LineInput(Decimal("1"), Decimal("-1"), False), {}),
        (LineInput(Decimal("1"), Decimal("1"), True, Decimal("101")), {}),
        (
            LineInput(Decimal("1"), Decimal("10"), False),
            {"discount_type": "fixed", "discount_value": Decimal("11")},
        ),
        (
            LineInput(Decimal("1"), Decimal("10"), False),
            {"deposit_type": "percentage", "deposit_value": Decimal("101")},
        ),
    ),
)
def test_invalid_financial_inputs_are_rejected(line, kwargs):
    with pytest.raises(ValueError):
        calculate_estimate((line,), **kwargs)


def test_zero_line_document_is_valid_for_a_draft():
    result = calculate_estimate(())

    assert result.lines == ()
    assert result.total == Decimal("0.00")


def test_discount_rounding_residual_never_exceeds_a_small_final_line():
    lines = tuple(
        [LineInput(Decimal("1"), Decimal("1.00"), False) for _ in range(100)]
        + [LineInput(Decimal("1"), Decimal("0.01"), False)]
    )

    result = calculate_estimate(
        lines,
        discount_type="fixed",
        discount_value=Decimal("99.99"),
    )

    assert sum(
        (line.allocated_discount for line in result.lines), Decimal("0")
    ) == Decimal("99.99")
    assert all(line.allocated_discount <= line.line_subtotal for line in result.lines)
    assert result.total == Decimal("0.02")
