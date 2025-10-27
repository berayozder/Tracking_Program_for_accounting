"""Database helpers package for the Tracking Program for accounting.

This package provides a small, stable public surface for code that previously
imported directly from the legacy ``db.py`` module. During a phased refactor
we keep these lightweight re-exports here so callers can continue to use
``from db import get_conn`` (for example) while implementations move into
smaller modules under :mod:`db` (for example :mod:`db.connection`,
:mod:`db.imports_dao`, :mod:`db.settings`).

All imports are attempted lazily and wrapped in try/except blocks so importing
the package is safe even if a specific submodule hasn't been created yet.
Only successfully imported symbols are added to :data:`__all__`.
"""

__all__ = []

# Connection helpers
try:
	from .connection import get_conn, init_db, DB_PATH,get_cursor # type: ignore
except Exception:
	# keep package importable even if module isn't present yet
	get_conn = None  # type: ignore
	init_db = None  # type: ignore
	DB_PATH = None  # type: ignore
	get_cursor = None  # type: ignore
else:
	__all__.extend(["get_conn", "init_db", "DB_PATH", "get_cursor"])

# Settings helpers
try:
	from .settings import (
		get_setting,
		set_setting,
		get_base_currency,
		get_default_import_currency,
		get_default_sale_currency,
		get_default_expense_currency,
	)  # type: ignore
except Exception:
	pass
else:
	__all__.extend([
		"get_setting",
		"set_setting",
		"get_base_currency",
		"get_default_import_currency",
		"get_default_sale_currency",
		"get_default_expense_currency",
	])
    
# Audit and crypto helpers
try:
	from .audit import write_audit,get_audit_distinct,get_audit_logs
except Exception:
	write_audit = None
	get_audit_distinct = None
	get_audit_logs = None
else:
	__all__.extend(["write_audit", "get_audit_distinct", "get_audit_logs"])


try:
	from .crypto import encrypt_str, decrypt_str  # type: ignore
except Exception:
	encrypt_str = None  # type: ignore
	decrypt_str = None  # type: ignore
else:
	__all__.extend(["encrypt_str", "decrypt_str"])

try:
    from .auth import (_pbkdf2_hash,
                       create_user,
                       users_exist,
                       verify_user,
                       set_current_user,
                       get_current_user,
                       require_admin)
except Exception:
    users_exist = None # type: ignore
    create_user = None  # type: ignore
    verify_user  = None  # type: ignore
    set_current_user = None  # type: ignore
    get_current_user = None  # type: ignore
    require_admin = None  # type: ignore
else:
    __all__.extend(["users_exist", "create_user", "verify_user", "set_current_user", "get_current_user", "require_admin"])

try:
    from .sales_dao import (list_sales,add_sale,
                            overwrite_sales,
                            get_distinct_sale_platforms,
                            undelete_sales_by_ids,
                            undelete_sales_by_indices,
                            mark_sale_deleted,
                            update_sale)
except Exception:
    list_sales = None  # type: ignore
    add_sale = None  # type: ignore
    overwrite_sales = None  # type: ignore
    get_distinct_sale_platforms = None  # type: ignore
    undelete_sales_by_ids = None  # type: ignore
    undelete_sales_by_indices = None  # type: ignore
    mark_sale_deleted = None  # type: ignore
    update_sale = None  # type: ignore
else:
    __all__.extend(["list_sales","add_sale","overwrite_sales","get_distinct_sale_platforms","undelete_sales_by_ids","undelete_sales_by_indices","mark_sale_deleted","update_sale"])

try: 
    from .schema import init_db_schema,add_column_if_missing
except Exception:
    init_db_schema = None  # type: ignore
    add_column_if_missing = None  # type: ignore
else:
    __all__.extend(["init_db_schema", "add_column_if_missing"])


try:
    from .soft_delete import (soft_delete_entity, restore_entity, void_transaction, void_sale)
except Exception:
    soft_delete_entity = None
    restore_entity = None
    void_transaction = None
    void_sale = None
else:
    __all__.extend(["soft_delete_entity", "restore_entity", "void_transaction", "void_sale"])


try:
    from .expenses_dao import (add_expense, 
                               get_expenses,
                               edit_expense,
                               get_expense_import_links,
                               delete_expense,
                               undelete_expense)
except Exception:
    add_expense = None  # type: ignore
    get_expenses = None  # type: ignore
    edit_expense = None  # type: ignore
    get_expense_import_links = None  # type: ignore
    delete_expense = None  # type: ignore
    undelete_expense = None  # type: ignore
else:
    __all__.extend(["add_expense", "get_expenses", "edit_expense", "get_expense_import_links", "delete_expense", "undelete_expense"])
    
try:
    from .returns_dao import (list_returns,
                              insert_return,
                              _compute_refund_base,
                              update_return,
                              delete_return,
                              undelete_return,
                              get_distinct_return_reasons)
except Exception:
    insert_return = None  # type: ignore
    get_returns = None  # type: ignore
    _compute_refund_base = None  # type: ignore
    update_return = None  # type: ignore
    delete_return = None  # type: ignore
    undelete_return = None  # type: ignore
    get_distinct_return_reasons = None  # type: ignore
else:
    __all__.extend(["insert_return", "get_returns", "_compute_refund_base", "update_return", "delete_return", "undelete_return", "get_distinct_return_reasons"])


try:
    from .rates import get_cached_rate, set_cached_rate,convert_amount,_get_rate_generic,get_rate_to_base
except Exception:
    get_cached_rate = None  # type: ignore
    set_cached_rate = None  # type: ignore
    convert_amount = None  # type: ignore
    _get_rate_generic = None  # type: ignore
    get_rate_to_base = None  # type: ignore
else:
    __all__.extend(["get_cached_rate", "set_cached_rate", "convert_amount", "_get_rate_generic", "get_rate_to_base"])

try:
    from .product_codes_dao import get_product_code, set_product_code, get_cat_code_for_category, generate_product_ids, get_all_product_codes, update_next_serial, delete_product_code
    __all__.extend(["get_product_code","set_product_code","get_cat_code_for_category","generate_product_ids","get_all_product_codes","update_next_serial","delete_product_code"])
except Exception as e:
    get_product_code = None  # type: ignore
    set_product_code = None  # type: ignore
    get_cat_code_for_category = None  # type: ignore
    generate_product_ids = None  # type: ignore
    get_all_product_codes = None  # type: ignore
    update_next_serial = None  # type: ignore
    delete_product_code = None  # type: ignore

try:
    from .inventory_dao import get_inventory,rebuild_inventory_from_imports,update_inventory
except Exception:   
    get_inventory = None  # type: ignore
    rebuild_inventory_from_imports = None  # type: ignore
    update_inventory = None  # type: ignore
else:
    __all__.append("get_inventory")
    __all__.append("rebuild_inventory_from_imports")
    __all__.append("update_inventory")

try:
    from .imports_dao import (add_import,
                            create_import_batch,
                            get_imports,get_imports_with_lines,
                            edit_import,
                            delete_import,undelete_import,
                            get_available_batches,
                            allocate_sale_to_batches,
                            backfill_allocation_unit_costs,
                            undelete_allocation,
                            get_sale_batch_info, 
                            handle_return_batch_allocation,
                            migrate_existing_imports_to_batches,recompute_import_batches)
except Exception as e:
    print("[IMPORT ERROR] Failed to import from imports_dao:", e)
    add_import = None  # type: ignore
    create_import_batch = None  # type: ignore
    get_imports = None  # type: ignore
    get_imports_with_lines = None  # type: ignore
    edit_import = None  # type: ignore
    recompute_import_batches = None  # type: ignore
    delete_import = None  # type: ignore
    undelete_import = None  # type: ignore
    get_available_batches = None  # type: ignore
    allocate_sale_to_batches = None  # type: ignore
    backfill_allocation_unit_costs = None  # type: ignore
    undelete_allocation = None  # type: ignore
    get_sale_batch_info = None  # type: ignore
    handle_return_batch_allocation = None  # type: ignore
    migrate_existing_imports_to_batches = None  # type: ignore
else:
    __all__.extend(["add_import","create_import_batch","get_imports","get_imports_with_lines","edit_import","delete_import","undelete_import","get_available_batches","allocate_sale_to_batches","backfill_allocation_unit_costs","undelete_allocation","get_sale_batch_info","handle_return_batch_allocation","migrate_existing_imports_to_batches","recompute_import_batches"])


# Analytics helpers (export safe wrappers so callers can use db.<name>)
try:
    from .analytics_dao import (
        get_profit_analysis_by_sale,
        get_monthly_sales_profit,
        get_monthly_imports_value,
        get_monthly_expenses,
        get_yearly_sales_profit,
        get_yearly_expenses,
        get_yearly_return_impact,
        get_monthly_return_impact,
        get_yearly_imports_value,
        build_monthly_overview,
        build_yearly_summary,
        get_batch_utilization_report,
        get_batch_utilization_report_inclusive,
    )  # type: ignore
except Exception:
    get_profit_analysis_by_sale = None  # type: ignore
    get_monthly_sales_profit = None  # type: ignore
    get_monthly_imports_value = None  # type: ignore
    get_monthly_expenses = None  # type: ignore
    get_yearly_sales_profit = None  # type: ignore
    get_yearly_expenses = None  # type: ignore
    get_yearly_return_impact = None  # type: ignore
    get_monthly_return_impact = None  # type: ignore
    get_yearly_imports_value = None  # type: ignore
    build_monthly_overview = None  # type: ignore
    build_yearly_summary = None  # type: ignore
    get_batch_utilization_report = None  # type: ignore
    get_batch_utilization_report_inclusive = None  # type: ignore
else:
    __all__.extend([
        "get_profit_analysis_by_sale",
        "get_monthly_sales_profit",
        "get_monthly_imports_value",
        "get_monthly_expenses",
        "get_yearly_sales_profit",
        "get_yearly_expenses",
        "get_yearly_return_impact",
        "get_monthly_return_impact",
        "get_yearly_imports_value",
        "build_monthly_overview",
        "build_yearly_summary",
        "get_batch_utilization_report",
        "get_batch_utilization_report_inclusive",
    ])

# Customers helpers (guarded exports so callers can use db.<name>)
try:
    from .customers_dao import (
        get_next_customer_id,
        add_customer,
        read_customers,
        write_customers,
        find_customer_by_name,
    # find_or_create_customer,  # Removed: not implemented
    # get_customer_name_suggestions,  # Removed: not implemented
        edit_customer,
        delete_customer,
        get_customer_sales_summary,
    )  # type: ignore
except Exception as e:
    print("[db/__init__.py] Error importing customers_dao:", e)
    import traceback; traceback.print_exc()
    get_next_customer_id = None  # type: ignore
    add_customer = None  # type: ignore
    read_customers = None  # type: ignore
    write_customers = None  # type: ignore
    find_customer_by_name = None  # type: ignore
    find_or_create_customer = None  # type: ignore
    get_customer_name_suggestions = None  # type: ignore
    edit_customer = None  # type: ignore
    delete_customer = None  # type: ignore
    get_customer_sales_summary = None  # type: ignore
else:
    __all__.extend([
        "get_next_customer_id",
        "add_customer",
        "read_customers",
        "write_customers",
        "find_customer_by_name",
    # "find_or_create_customer",  # Removed: not implemented
    # "get_customer_name_suggestions",  # Removed: not implemented
        "edit_customer",
        "delete_customer",
        "get_customer_sales_summary",
    ])



# Expose the public API as a tuple for introspection if desired
__all__ = tuple(__all__)

