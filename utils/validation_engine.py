"""IMPROVEMENT 7: Validation Rules Engine"""
from db.database import record_validation_issue, get_unresolved_issues
from datetime import datetime


class ValidationRule:
    def __init__(self, rule_id: str, description: str, severity: str = "warning"):
        self.rule_id = rule_id
        self.description = description
        self.severity = severity

    def validate(self, container_data: dict) -> list[str]:
        """Return list of violations (empty if valid)."""
        raise NotImplementedError


class DateSequenceRule(ValidationRule):
    """ETD must be before ETA"""
    def __init__(self):
        super().__init__("date_sequence", "Shipment date must be before arrival date", "error")

    def validate(self, container_data: dict) -> list[str]:
        etd = container_data.get("etd")
        eta = container_data.get("eta")
        if etd and eta and etd >= eta:
            return [f"ETD ({etd}) should be before ETA ({eta})"]
        return []


class DeliveryDateRule(ValidationRule):
    """Delivery date should be after arrival"""
    def __init__(self):
        super().__init__("delivery_sequence", "Delivery date should be after arrival date", "warning")

    def validate(self, container_data: dict) -> list[str]:
        eta = container_data.get("eta")
        delivery = container_data.get("date_livraison")
        if eta and delivery and delivery < eta:
            return [f"Delivery date ({delivery}) should be after ETA ({eta})"]
        return []


class SurestarioeDaysRule(ValidationRule):
    """Surestarie days should be non-negative"""
    def __init__(self):
        super().__init__("surestarie_positive", "Surestarie days should be non-negative", "warning")

    def validate(self, container_data: dict) -> list[str]:
        days = container_data.get("nbr_jours_surestarie_estimes", 0)
        if days < 0:
            return [f"Estimated surestarie days ({days}) cannot be negative"]
        return []


class ContainerNumberFormatRule(ValidationRule):
    """Container number must be 4 letters + 7 digits"""
    def __init__(self):
        super().__init__("container_format", "Container number must be valid format (4 letters + 7 digits)", "error")

    def validate(self, container_data: dict) -> list[str]:
        cnum = container_data.get("container_number", "")
        import re
        if not re.match(r"^[A-Z]{3,4}\d{6,7}$", cnum):
            return [f"Container number '{cnum}' is invalid format"]
        return []


class TanNumberFormatRule(ValidationRule):
    """TAN should follow TAN/XXXX/YYYY format"""
    def __init__(self):
        super().__init__("tan_format", "TAN should be in format TAN/XXXX/YYYY", "warning")

    def validate(self, container_data: dict) -> list[str]:
        tan = container_data.get("tan_number")
        if tan:
            import re
            if not re.match(r"^TAN/\d{4}/\d{4}$", tan):
                return [f"TAN '{tan}' does not follow standard format"]
        return []


# Registry of all validation rules
VALIDATION_RULES = [
    DateSequenceRule(),
    DeliveryDateRule(),
    SurestarioeDaysRule(),
    ContainerNumberFormatRule(),
    TanNumberFormatRule(),
]


def validate_container(container_data: dict, container_id: int = None, shipment_id: int = None) -> dict:
    """Run all validation rules against container data. Returns summary and issues."""
    issues = []

    for rule in VALIDATION_RULES:
        violations = rule.validate(container_data)
        for violation in violations:
            issues.append({
                "rule_id": rule.rule_id,
                "description": violation,
                "severity": rule.severity,
            })
            if container_id or shipment_id:
                record_validation_issue(
                    issue_type=rule.rule_id,
                    field_name=None,
                    issue_desc=violation,
                    severity=rule.severity,
                    container_id=container_id,
                    shipment_id=shipment_id,
                )

    return {
        "is_valid": len([i for i in issues if i["severity"] == "error"]) == 0,
        "error_count": len([i for i in issues if i["severity"] == "error"]),
        "warning_count": len([i for i in issues if i["severity"] == "warning"]),
        "issues": issues,
    }


def get_validation_status(container_id: int) -> dict:
    """Get validation status for a container."""
    issues = get_unresolved_issues(container_id=container_id)
    return {
        "total_issues": len(issues),
        "errors": len([i for i in issues if i["severity"] == "error"]),
        "warnings": len([i for i in issues if i["severity"] == "warning"]),
        "issues": issues,
    }
