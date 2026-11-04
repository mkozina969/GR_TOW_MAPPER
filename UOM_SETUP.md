# Packaging conversion

1. Run `migrations/001_item_uom_conversion.sql` against the GR Neon database configured by `GR_DATABASE_URL` before releasing the app. Alternatively, after deploying, unlock Admin and click **Initialize UoM table**. Mapping fails closed until the table exists.
2. In Admin → UoM Conversion, enter the exact vendor ID, supplier item code, integer divider and active status. Save the same keys to edit or disable a rule.
3. Select the vendor, upload the original document and select the supplier and quantity columns. For packing lists, leave Unit price column at **(no price)**. For invoices, select the unit price column. Click Run mapping. Active rules for the selected vendor divide the quantity and multiply the price when supplied. Rows without a matching rule stay unchanged.
4. Review the conversion audit and export. Packing lists can use Pallets PRN. For Portal CSV after a quantity-only conversion, rerun mapping with the invoice's unit price column. Invalid numbers or non-divisible quantities block the batch. Correct the document or rule and rerun.

Calculations and line-value checks use Decimal. Excel exports numeric cells using Excel's usual floating-point precision. Source uploads are never modified; every rerun starts from the source. Exported files must not be uploaded as original supplier invoices, since their unchanged column format cannot identify prior conversion.

Example: 12 PCS at 2.50 with divider 3 becomes 4 SET at 7.50; total remains 30.00. No example rules are inserted automatically.

Validation: `python -m unittest test_uom_conversion -v`.
