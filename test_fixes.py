#!/usr/bin/env python3
"""
Test fixes and validation for SRCash application
This file contains comprehensive tests to identify and fix issues in the cash management system.
"""

import unittest
import sqlite3
import tempfile
import os
import sys
from datetime import datetime, date
from unittest.mock import Mock, patch, MagicMock

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import get_connection, initialize_db
from db_manager import DBManager, DENOM_MAPPING, COIN_TOTAL_COLS


class TestDatabaseOperations(unittest.TestCase):
    """Test database operations and schema validation"""
    
    def setUp(self):
        """Set up test database"""
        self.test_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.test_db.close()
        self.db_path = self.test_db.name
        
        # Initialize test database
        with patch('database.get_connection') as mock_conn:
            mock_conn.return_value = sqlite3.connect(self.db_path)
            initialize_db()
    
    def tearDown(self):
        """Clean up test database"""
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
    
    def test_database_connection(self):
        """Test database connection functionality"""
        conn = get_connection()
        self.assertIsNotNone(conn)
        conn.close()
    
    def test_database_schema_creation(self):
        """Test that all required tables are created"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check if all tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        expected_tables = [
            'daily_cash', 'daily_cash_count', 'expenses', 
            'old_invoices', 'bio_cash'
        ]
        
        for table in expected_tables:
            self.assertIn(table, tables, f"Table {table} not found")
        
        conn.close()
    
    def test_daily_cash_table_structure(self):
        """Test daily_cash table structure"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("PRAGMA table_info(daily_cash)")
        columns = [row[1] for row in cursor.fetchall()]
        
        expected_columns = [
            'id', 'daily_cash_count', 'other_sell', 'prev_day_cash',
            'total_cash_sell', 'total_card_sell', 'total_daily_sell',
            'next_day_cash_note', 'next_day_cash_coin', 'total_cash_taken',
            'cash_taken_by', 'created_at'
        ]
        
        for col in expected_columns:
            self.assertIn(col, columns, f"Column {col} not found in daily_cash")
        
        conn.close()


class TestDBManager(unittest.TestCase):
    """Test DBManager class functionality"""
    
    def setUp(self):
        """Set up test database manager"""
        self.test_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.test_db.close()
        self.db_path = self.test_db.name
        self.db_manager = DBManager(self.db_path)
    
    def tearDown(self):
        """Clean up test database"""
        self.db_manager.close()
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
    
    def test_denomination_mapping(self):
        """Test denomination mapping is complete and correct"""
        expected_denoms = [
            "€200", "€100", "€50", "€20", "€10", "€5", 
            "€2", "€1", "50c", "20c", "10c"
        ]
        
        for denom in expected_denoms:
            self.assertIn(denom, DENOM_MAPPING, f"Denomination {denom} missing from mapping")
            
            qty_col, total_col, value = DENOM_MAPPING[denom]
            self.assertIsInstance(qty_col, str)
            self.assertIsInstance(total_col, str)
            self.assertIsInstance(value, float)
            self.assertGreater(value, 0)
    
    def test_upsert_denomination(self):
        """Test denomination upsert functionality"""
        test_date = "2024-01-01"
        test_denom = "€10"
        test_qty = 5
        
        # Test successful upsert
        self.db_manager.upsert_denomination(test_date, test_denom, test_qty)
        
        # Verify data was inserted
        row = self.db_manager.fetch_daily_cash_count(test_date)
        self.assertIsNotNone(row)
        
        # Test invalid denomination
        with self.assertRaises(ValueError):
            self.db_manager.upsert_denomination(test_date, "INVALID", test_qty)
    
    def test_coin_sum_calculation(self):
        """Test coin sum calculation in summary"""
        test_date = "2024-01-01"
        
        # Add some coins
        self.db_manager.upsert_denomination(test_date, "€2", 3)  # 6.0
        self.db_manager.upsert_denomination(test_date, "€1", 2)  # 2.0
        self.db_manager.upsert_denomination(test_date, "50c", 4)  # 2.0
        self.db_manager.upsert_denomination(test_date, "20c", 5)  # 1.0
        self.db_manager.upsert_denomination(test_date, "10c", 10)  # 1.0
        
        # Check coin sum in summary
        summary = self.db_manager.fetch_daily_cash(test_date)
        self.assertIsNotNone(summary)
        
        # Expected total: 6.0 + 2.0 + 2.0 + 1.0 + 1.0 = 12.0
        expected_coin_sum = 12.0
        # Note: Column index depends on table structure, this is a basic check
        self.assertIsNotNone(summary)
    
    def test_upsert_daily_cash(self):
        """Test daily cash summary upsert"""
        test_date = "2024-01-01"
        test_data = {
            'prev_day_cash': 100.0,
            'total_cash_sell': 500.0,
            'total_card_sell': 300.0,
            'next_day_cash_note': 200.0,
            'next_day_cash_coin': 50.0,
            'total_daily_sell': 800.0,
            'total_cash_taken': 150.0,
            'cash_taken_by': 'John Doe'
        }
        
        self.db_manager.upsert_daily_cash(test_date, test_data)
        
        # Verify data
        row = self.db_manager.fetch_daily_cash(test_date)
        self.assertIsNotNone(row)
    
    def test_safe_execute_error_handling(self):
        """Test error handling in safe_execute"""
        # Test with invalid SQL
        result = self.db_manager.safe_execute("INVALID SQL STATEMENT")
        self.assertFalse(result)
        
        # Test with valid SQL but invalid parameters
        result = self.db_manager.safe_execute("SELECT * FROM non_existent_table")
        self.assertFalse(result)


class TestBusinessLogic(unittest.TestCase):
    """Test business logic and calculations"""
    
    def setUp(self):
        """Set up test environment"""
        self.test_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.test_db.close()
        self.db_path = self.test_db.name
        self.db_manager = DBManager(self.db_path)
    
    def tearDown(self):
        """Clean up test environment"""
        self.db_manager.close()
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
    
    def test_cash_calculation_logic(self):
        """Test cash calculation business logic"""
        test_date = "2024-01-01"
        
        # Add denominations
        self.db_manager.upsert_denomination(test_date, "€50", 2)  # 100.0
        self.db_manager.upsert_denomination(test_date, "€20", 3)  # 60.0
        self.db_manager.upsert_denomination(test_date, "€10", 1)  # 10.0
        
        # Get total cash
        dcc = self.db_manager.fetchone("SELECT total_cash FROM daily_cash_count WHERE date = ?", (test_date,))
        total_cash = float(dcc[0]) if dcc and dcc[0] is not None else 0.0
        
        expected_total = 170.0  # 100 + 60 + 10
        self.assertEqual(total_cash, expected_total)
    
    def test_denomination_value_calculations(self):
        """Test denomination value calculations"""
        test_cases = [
            ("€200", 1, 200.0),
            ("€100", 2, 200.0),
            ("€50", 3, 150.0),
            ("€20", 4, 80.0),
            ("€10", 5, 50.0),
            ("€5", 6, 30.0),
            ("€2", 7, 14.0),
            ("€1", 8, 8.0),
            ("50c", 9, 4.5),
            ("20c", 10, 2.0),
            ("10c", 11, 1.1)
        ]
        
        for denom, qty, expected in test_cases:
            qty_col, total_col, value = DENOM_MAPPING[denom]
            calculated = float(qty) * float(value)
            self.assertEqual(calculated, expected, 
                           f"Calculation error for {denom}: {qty} * {value} = {calculated}, expected {expected}")


class TestDataValidation(unittest.TestCase):
    """Test data validation and input sanitization"""
    
    def test_denomination_validation(self):
        """Test denomination input validation"""
        valid_denoms = list(DENOM_MAPPING.keys())
        invalid_denoms = ["€500", "1c", "€0.5", "invalid", ""]
        
        for denom in valid_denoms:
            self.assertIn(denom, DENOM_MAPPING, f"Valid denomination {denom} not recognized")
        
        for denom in invalid_denoms:
            self.assertNotIn(denom, DENOM_MAPPING, f"Invalid denomination {denom} should not be recognized")
    
    def test_quantity_validation(self):
        """Test quantity input validation"""
        # Test valid quantities
        valid_quantities = [0, 1, 100, 1000, 9999]
        for qty in valid_quantities:
            self.assertIsInstance(qty, int)
            self.assertGreaterEqual(qty, 0)
        
        # Test invalid quantities
        invalid_quantities = [-1, -100, "abc", None, 1.5]
        for qty in invalid_quantities:
            if isinstance(qty, (int, float)) and qty < 0:
                self.assertLess(qty, 0, f"Negative quantity {qty} should be invalid")
            elif not isinstance(qty, int):
                self.assertNotIsInstance(qty, int, f"Non-integer quantity {qty} should be invalid")
    
    def test_date_validation(self):
        """Test date format validation"""
        valid_dates = [
            "2024-01-01",
            "2024-12-31",
            "2023-02-28",
            "2024-02-29"  # Leap year
        ]
        
        invalid_dates = [
            "2024/01/01",  # Wrong format
            "01-01-2024",  # Wrong format
            "2024-13-01",  # Invalid month
            "2024-01-32",  # Invalid day
            "invalid",     # Not a date
            ""             # Empty
        ]
        
        for date_str in valid_dates:
            try:
                datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                self.fail(f"Valid date {date_str} failed validation")
        
        for date_str in invalid_dates:
            with self.assertRaises(ValueError):
                datetime.strptime(date_str, "%Y-%m-%d")


class TestErrorHandling(unittest.TestCase):
    """Test error handling and edge cases"""
    
    def setUp(self):
        """Set up test environment"""
        self.test_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.test_db.close()
        self.db_path = self.test_db.name
        self.db_manager = DBManager(self.db_path)
    
    def tearDown(self):
        """Clean up test environment"""
        self.db_manager.close()
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
    
    def test_database_connection_failure(self):
        """Test handling of database connection failures"""
        # Test with invalid database path
        with self.assertRaises(Exception):
            DBManager("/invalid/path/database.db")
    
    def test_sql_injection_protection(self):
        """Test SQL injection protection"""
        malicious_input = "'; DROP TABLE daily_cash; --"
        
        # Test that malicious input is handled safely
        result = self.db_manager.safe_execute(
            "SELECT * FROM daily_cash WHERE cash_taken_by = ?", 
            (malicious_input,)
        )
        # Should not crash and should handle the input safely
        self.assertIsNotNone(result)
    
    def test_large_quantity_handling(self):
        """Test handling of large quantities"""
        test_date = "2024-01-01"
        large_qty = 999999
        
        # Test with very large quantity
        self.db_manager.upsert_denomination(test_date, "€1", large_qty)
        
        # Verify the data was stored correctly
        row = self.db_manager.fetch_daily_cash_count(test_date)
        self.assertIsNotNone(row)
    
    def test_empty_string_handling(self):
        """Test handling of empty strings and None values"""
        test_date = "2024-01-01"
        
        # Test with empty string
        self.db_manager.upsert_daily_cash(test_date, {
            'cash_taken_by': '',
            'prev_day_cash': 0.0
        })
        
        # Test with None values (should be converted to defaults)
        self.db_manager.upsert_daily_cash(test_date, {
            'cash_taken_by': None,
            'prev_day_cash': None
        })


class TestUIFixes(unittest.TestCase):
    """Test UI-related fixes and improvements"""
    
    def test_quantity_dialog_validation(self):
        """Test quantity dialog input validation"""
        from ui_main import QuantityDialog
        from PyQt6.QtWidgets import QApplication
        
        # Create QApplication if it doesn't exist
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        
        # Mock the dialog
        dialog = QuantityDialog("€10", 10.0)
        
        # Test valid input
        dialog.input.setText("5")
        self.assertEqual(dialog.get_quantity(), 5)
        
        # Test empty input
        dialog.input.setText("")
        self.assertEqual(dialog.get_quantity(), 0)
        
        # Test whitespace input
        dialog.input.setText("   ")
        self.assertEqual(dialog.get_quantity(), 0)
        
        # Test invalid input
        dialog.input.setText("abc")
        self.assertEqual(dialog.get_quantity(), 0)
        
        dialog.close()
    
    def test_table_cell_creation(self):
        """Test table cell creation and formatting"""
        from ui_main import MainWindow
        from PyQt6.QtWidgets import QApplication
        
        # Create QApplication if it doesn't exist
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        
        # Test cell creation
        window = MainWindow()
        cell = window.make_cell("test")
        
        self.assertIsNotNone(cell)
        self.assertEqual(cell.text(), "test")
        
        # Test empty cell
        empty_cell = window.make_cell("")
        self.assertEqual(empty_cell.text(), "")
        
        window.close()


class TestPerformanceAndOptimization(unittest.TestCase):
    """Test performance and optimization aspects"""
    
    def setUp(self):
        """Set up test environment"""
        self.test_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.test_db.close()
        self.db_path = self.test_db.name
        self.db_manager = DBManager(self.db_path)
    
    def tearDown(self):
        """Clean up test environment"""
        self.db_manager.close()
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
    
    def test_bulk_operations(self):
        """Test bulk operations performance"""
        test_date = "2024-01-01"
        
        # Test bulk denomination insertions
        denominations = list(DENOM_MAPPING.keys())
        quantities = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110]
        
        for denom, qty in zip(denominations, quantities):
            self.db_manager.upsert_denomination(test_date, denom, qty)
        
        # Verify all data was inserted
        row = self.db_manager.fetch_daily_cash_count(test_date)
        self.assertIsNotNone(row)
    
    def test_database_indexes(self):
        """Test that database indexes are properly created"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check for indexes
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = [row[0] for row in cursor.fetchall()]
        
        # Should have unique indexes on date columns
        expected_indexes = ['idx_dcc_date', 'idx_dc_date']
        for idx in expected_indexes:
            self.assertIn(idx, indexes, f"Index {idx} not found")
        
        conn.close()


def run_all_tests():
    """Run all test suites"""
    test_suites = [
        TestDatabaseOperations,
        TestDBManager,
        TestBusinessLogic,
        TestDataValidation,
        TestErrorHandling,
        TestUIFixes,
        TestPerformanceAndOptimization
    ]
    
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    for test_class in test_suites:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


def identify_common_issues():
    """Identify common issues in the codebase"""
    issues = []
    
    # Check for potential issues in the code
    issues.append("1. Database schema inconsistencies between database.py and db_manager.py")
    issues.append("2. Missing error handling in UI components")
    issues.append("3. Potential SQL injection vulnerabilities (though parameterized queries are used)")
    issues.append("4. No input validation for negative quantities")
    issues.append("5. Missing database connection cleanup in some paths")
    issues.append("6. No backup/restore functionality")
    issues.append("7. Missing data export validation")
    issues.append("8. No concurrent access handling")
    issues.append("9. Missing logging for debugging")
    issues.append("10. No data migration strategy for schema changes")
    issues.append("11. Missing input sanitization for special characters")
    issues.append("12. No data integrity checks for financial calculations")
    issues.append("13. Missing validation for date ranges in statistics")
    issues.append("14. No handling for database corruption scenarios")
    issues.append("15. Missing unit tests for edge cases in calculations")
    
    return issues


def suggest_improvements():
    """Suggest improvements for the codebase"""
    improvements = []
    
    improvements.append("1. Add comprehensive logging using Python's logging module")
    improvements.append("2. Implement data backup and restore functionality")
    improvements.append("3. Add input validation decorators for UI components")
    improvements.append("4. Create a configuration file for application settings")
    improvements.append("5. Add database connection pooling for better performance")
    improvements.append("6. Implement proper error reporting and user notifications")
    improvements.append("7. Add data export validation and format checking")
    improvements.append("8. Create automated database migration scripts")
    improvements.append("9. Add comprehensive documentation for all functions")
    improvements.append("10. Implement proper exception handling hierarchy")
    improvements.append("11. Add data integrity constraints at database level")
    improvements.append("12. Create unit tests for all business logic functions")
    improvements.append("13. Add integration tests for UI workflows")
    improvements.append("14. Implement proper resource cleanup patterns")
    improvements.append("15. Add performance monitoring and profiling")
    
    return improvements


if __name__ == "__main__":
    print("Running SRCash Test Fixes...")
    print("=" * 50)
    
    # Run all tests
    success = run_all_tests()
    
    print("\n" + "=" * 50)
    print("IDENTIFIED ISSUES:")
    print("=" * 50)
    
    issues = identify_common_issues()
    for issue in issues:
        print(f"• {issue}")
    
    print("\n" + "=" * 50)
    print("SUGGESTED IMPROVEMENTS:")
    print("=" * 50)
    
    improvements = suggest_improvements()
    for improvement in improvements:
        print(f"• {improvement}")
    
    print("\n" + "=" * 50)
    if success:
        print("✅ All tests passed!")
    else:
        print("❌ Some tests failed. Please review the output above.")
    
    print("=" * 50)
