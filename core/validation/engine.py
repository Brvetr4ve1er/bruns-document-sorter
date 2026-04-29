import re

class ValidationRule:
    def __init__(self, rule_id: str, description: str, severity: str = "warning"):
        self.rule_id = rule_id
        self.description = description
        self.severity = severity

    def validate(self, data: dict) -> list[str]:
        """Return list of violations (empty if valid)."""
        raise NotImplementedError

class DateSequenceRule(ValidationRule):
    """ETD must be before ETA"""
    def __init__(self):
        super().__init__("date_sequence", "Shipment date must be before arrival date", "error")

    def validate(self, data: dict) -> list[str]:
        etd = data.get("etd")
        eta = data.get("eta")
        if etd and eta and etd >= eta:
            return [f"ETD ({etd}) should be before ETA ({eta})"]
        return []

class DeliveryDateRule(ValidationRule):
    """Delivery date should be after arrival"""
    def __init__(self):
        super().__init__("delivery_sequence", "Delivery date should be after arrival date", "warning")

    def validate(self, data: dict) -> list[str]:
        eta = data.get("eta")
        delivery = data.get("date_livraison")
        if eta and delivery and delivery < eta:
            return [f"Delivery date ({delivery}) should be after ETA ({eta})"]
        return []

class SurestarioeDaysRule(ValidationRule):
    """Surestarie days should be non-negative"""
    def __init__(self):
        super().__init__("surestarie_positive", "Surestarie days should be non-negative", "warning")

    def validate(self, data: dict) -> list[str]:
        days = data.get("nbr_jours_surestarie_estimes", 0)
        if isinstance(days, (int, float)) and days < 0:
            return [f"Estimated surestarie days ({days}) cannot be negative"]
        return []

class ContainerNumberFormatRule(ValidationRule):
    """Container number must be 4 letters + 7 digits"""
    def __init__(self):
        super().__init__("container_format", "Container number must be valid format (4 letters + 7 digits)", "error")

    def validate(self, data: dict) -> list[str]:
        cnum = data.get("container_number", "")
        if cnum and not re.match(r"^[A-Z]{3,4}\d{6,7}$", str(cnum)):
            return [f"Container number '{cnum}' is invalid format"]
        return []

class TanNumberFormatRule(ValidationRule):
    """TAN should follow TAN/XXXX/YYYY format"""
    def __init__(self):
        super().__init__("tan_format", "TAN should be in format TAN/XXXX/YYYY", "warning")

    def validate(self, data: dict) -> list[str]:
        tan = data.get("tan_number")
        if tan and not re.match(r"^TAN/\d{4}/\d{4}$", str(tan)):
            return [f"TAN '{tan}' does not follow standard format"]
        return []

LOGISTICS_RULES = [
    DateSequenceRule(),
    DeliveryDateRule(),
    SurestarioeDaysRule(),
    ContainerNumberFormatRule(),
    TanNumberFormatRule(),
]

def validate_extraction(data: dict, module: str = "logistics") -> dict:
    """
    Run validation rules and return issues. Pure function, no DB side effects.
    """
    issues = []
    
    rules = LOGISTICS_RULES if module == "logistics" else []

    # Could be shipment data or container data
    # To handle lists of containers in a shipment:
    if "containers" in data and isinstance(data["containers"], list):
        for c in data["containers"]:
            for rule in rules:
                for violation in rule.validate(c):
                    issues.append({
                        "rule_id": rule.rule_id,
                        "description": violation,
                        "severity": rule.severity,
                        "entity": c.get("container_number", "Unknown Container")
                    })
    
    # Also run on the top-level data
    for rule in rules:
        for violation in rule.validate(data):
            issues.append({
                "rule_id": rule.rule_id,
                "description": violation,
                "severity": rule.severity,
                "entity": data.get("tan_number", "Shipment")
            })

    return {
        "is_valid": len([i for i in issues if i["severity"] == "error"]) == 0,
        "error_count": len([i for i in issues if i["severity"] == "error"]),
        "warning_count": len([i for i in issues if i["severity"] == "warning"]),
        "issues": issues,
    }
