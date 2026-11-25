import re


def normalize_tax_id(value: str, *, cnpj: bool = False) -> str:
    digits = re.sub(r"[. /-]", "", value.strip())
    size = 14 if cnpj else 11
    if not re.fullmatch(rf"[0-9]{{{size}}}", digits) or len(set(digits)) == 1:
        raise ValueError("Documento inválido")
    weights = (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2) if cnpj else tuple(range(10, 1, -1))
    for shift in range(2):
        current = ((6 if cnpj else 11), *weights) if shift else weights
        remainder = sum(int(digit) * weight for digit, weight in zip(digits, current, strict=False)) % 11
        check = 0 if remainder < 2 else 11 - remainder
        if int(digits[size - 2 + shift]) != check:
            raise ValueError("Documento inválido")
    return digits


def normalize_passport(value: str) -> str:
    normalized = re.sub(r"[ -]", "", value.strip()).upper()
    if not re.fullmatch(r"[A-Z0-9]{3,32}", normalized):
        raise ValueError("Passaporte inválido")
    return normalized
