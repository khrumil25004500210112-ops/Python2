"""PTMAE demo solution (corrected)."""


# ---------- Exceptions ----------
class BaseSystemError(Exception):
    pass


class CorruptedRecordError(BaseSystemError):
    pass


class OutOfBoundsError(BaseSystemError):
    pass


class InsufficientBalanceError(BaseSystemError):
    pass


# ---------- Unit 1: loops and arithmetic ----------
def compound_interest(principal, rate, years):
    """Return interest earned (not the final amount) after `years`."""
    amount = principal
    i = 0
    while i < years:
        amount = amount + amount * rate / 100
        i += 1
    return amount - principal


def penalty_fee(base_fee, days_late):
    """Fee grows by one base_fee multiple for every full week late; capped by modulo 10000."""
    fee = 0
    d = 0
    while d < days_late:
        fee = fee + base_fee * (1 + d // 7)
        d += 1
    return fee % 10000


def trajectory_guard(balance, transactions, threshold):
    """Apply transactions until a 'STOP' marker or the balance drops below threshold."""
    for t in transactions:
        if t == "STOP" or balance < threshold:
            break
        balance += t
    return balance


def interactive_loop():
    running = True
    while running:
        cmd = input("ptmae> ").strip()
        while cmd == "":
            cmd = input("ptmae> ").strip()
        if cmd == "exit":
            break
        print("unknown command:", cmd)


# ---------- Unit 2: parser and closures ----------
def parse_raw_log_line(line, delimiter=",", quote_char='"'):
    tokens = []
    field = ""
    in_quotes = False
    i = 0
    n = len(line)
    while i < n:
        ch = line[i]
        nxt = line[i + 1:i + 2]
        if in_quotes:
            if ch == quote_char and nxt == quote_char:
                field += quote_char
                i += 1
            elif ch == quote_char:
                in_quotes = False
            else:
                field += ch
        elif ch == quote_char:
            in_quotes = True
        elif ch == delimiter:
            tokens.append(field)
            field = ""
        else:
            field += ch
        i += 1
    tokens.append(field)
    return tokens


def create_audit_filter(threshold):
    audited = 0

    def validate(amount):
        nonlocal audited
        audited += 1
        return amount >= threshold

    return validate


def build_filters(n):
    # k=k binds the loop variable at definition time (avoids late-binding bug)
    return [lambda row, k=k: row[k] > 0 for k in range(n)]


# ---------- Unit 3: comprehensions and in-place mutation ----------
raw_db = {
    "BRANCH_01": [("Acc101", {"DEPOSIT", "UPI"}), ("Acc102", {"LOAN", "UPI"})],
    "BRANCH_02": [("Acc101", {"SAVINGS", "UPI"}), ("Acc103", {"CARD", "DEPOSIT"})],
}

all_tags = {t for rows in raw_db.values() for _, tags in rows for t in tags}

reverse_index = {
    tag: sorted({(acc, br)
                 for br, rows in raw_db.items()
                 for acc, tags in rows
                 if tag in tags})
    for tag in all_tags
}


def _sort_desc(lst):
    try:
        lst.sort(reverse=True)
    except TypeError:  # mixed, non-comparable types
        lst.sort(key=str, reverse=True)


def clean_transaction_queue(data_list):
    """In place: tuples -> lists, sets lose even ints, lists sorted descending,
    duplicate ints removed (first occurrence kept)."""
    for i in range(len(data_list)):
        item = data_list[i]
        if isinstance(item, tuple):
            item = list(item)
            data_list[i] = item
        if isinstance(item, set):
            item -= {x for x in item if isinstance(x, int) and x % 2 == 0}
        elif isinstance(item, list):
            _sort_desc(item)

    seen_ints = set()
    filtered = []
    for v in data_list:
        if isinstance(v, int):
            if v in seen_ints:
                continue
            seen_ints.add(v)
        filtered.append(v)
    data_list[:] = filtered


# ---------- Unit 4: file I/O ----------
def update_record(path, account_id, new_balance):
    """Rewrite the balance of `account_id` in a 'id,name,balance' file.
    Malformed lines are logged to corrupted.log. Missing files raise
    FileNotFoundError; other I/O failures raise CorruptedRecordError."""
    processed, rejected = 0, 0
    updated = False
    try:
        with open(path, "r+") as f:
            line_no = 0
            while True:
                pos = f.tell()
                line = f.readline()
                if not line:
                    break
                line_no += 1
                parts = parse_raw_log_line(line.strip())
                if len(parts) != 3:
                    rejected += 1
                    with open("corrupted.log", "a") as log:
                        log.write("line " + str(line_no) + ": " + line)
                    continue
                if parts[0] == account_id:
                    new_line = parts[0] + "," + parts[1] + "," + str(new_balance) + "\n"
                    rest = f.read()
                    f.seek(pos)
                    f.write(new_line + rest)
                    f.truncate()
                    processed += 1
                    updated = True
                    break
    except FileNotFoundError:
        raise
    except OSError as e:
        raise CorruptedRecordError(str(e)) from e
    else:
        if updated:
            with open("ledger.txt", "a") as led:
                led.write(account_id + " -> " + str(new_balance) + "\n")
    finally:
        print("Processed:", processed, "Rejected:", rejected)


# ---------- Unit 5: OOP ----------
class Account:
    total_accounts = 0

    def __init__(self, account_id, balance):
        self._account_id = account_id
        self.__balance = 0
        self.set_balance(balance)
        Account.total_accounts += 1

    def get_balance(self):
        return self.__balance

    def set_balance(self, value):
        if not isinstance(value, (int, float)):
            raise TypeError("balance must be numeric")
        self.__balance = value

    def process_settlement(self, amount):
        raise NotImplementedError


class SavingsAccount(Account):
    def process_settlement(self, amount):
        if self.get_balance() - amount < 1000:
            raise InsufficientBalanceError("below minimum 1000")
        self.set_balance(self.get_balance() - amount)


class CurrentAccount(Account):
    def __init__(self, account_id, balance, limit):
        super().__init__(account_id, balance)
        self.__overdraft_limit = limit

    def process_settlement(self, amount):
        if self.get_balance() - amount < -self.__overdraft_limit:
            raise OutOfBoundsError("overdraft exceeded")
        self.set_balance(self.get_balance() - amount)


class CreditAccount(Account):
    def __init__(self, account_id, balance, limit):
        super().__init__(account_id, balance)
        self.__credit_limit = limit

    def process_settlement(self, amount):
        total = amount * 1.025  # 2.5% surcharge
        if total > self.__credit_limit:
            raise OutOfBoundsError("credit limit exceeded")
        self.set_balance(self.get_balance() + total)


def execute_batch_settlement(account_list, transaction_amount):
    ok, failed = 0, 0
    for acc in account_list:
        try:
            acc.process_settlement(transaction_amount)
        except BaseSystemError:
            failed += 1
        else:
            ok += 1
    return ok, failed


if __name__ == "__main__":
    a = SavingsAccount("S1", 5000)
    print(a._Account__balance)  # name-mangled access demo
    print(execute_batch_settlement(
        [a, CurrentAccount("C1", 100, 500), CreditAccount("R1", 0, 10000)], 800))
