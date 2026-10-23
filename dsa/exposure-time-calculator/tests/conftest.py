def pytest_configure(config):
    config.addinivalue_line("markers", "slow: needs optional heavy dependencies (mwprop); skipped when absent")
