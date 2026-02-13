"""Blood test data fetcher."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import List

from sqlalchemy import text

from core.pydantic_schemas import ChartData, Dataset, DataQuery
from infrastructure.db import require_blood_session_factory, session_scope

from .base import BaseDataFetcher

logger = logging.getLogger(__name__)


class BloodDataFetcher(BaseDataFetcher):
    """Fetch blood metrics from the lab results database."""

    # Mapping from short metric names to exact database test_names
    METRIC_MAPPING = {
        # Hematology
        "white_blood_cells": "White Blood Cells (WBC)",
        "red_blood_cells": "Red Blood Cells (RBC)",
        "hemoglobin": "Hemoglobin",
        "hematocrit": "Hematocrit",
        "mcv": "MCV",
        "mch": "MCH",
        "mchc": "MCHC",
        "rdw": "RDW",
        "platelets": "Platelets",
        "neutrophils": "Neutrophils",
        "lymphocytes": "Lymphocytes",
        "monocytes": "Monocytes",
        "eosinophils": "Eosinophils",
        "basophils": "Basophils",
        "esr": "ESR (V.S.G.)",
        "mpv": "MPV",
        "pct": "PCT",
        "pdw": "PDW",

        # Biochemistry
        "glucose": "Glucose",
        "hba1c": "HbA1c",
        "urea": "Urea",
        "bun": "BUN",
        "creatinine": "Creatinine",
        "egfr": "eGFR",
        "uric_acid": "Uric Acid",
        "total_cholesterol": "Total Cholesterol",
        "hdl_cholesterol": "HDL Cholesterol",
        "ldl_cholesterol": "LDL Cholesterol",
        "triglycerides": "Triglycerides",
        "ast": "AST (GOT)",
        "alt": "ALT (GPT)",
        "gamma_gt": "Gamma-GT (GGT)",
        "alkaline_phosphatase": "Alkaline Phosphatase (ALP)",
        "total_proteins": "Total Proteins",
        "albumin": "Albumin",
        "crp": "C-Reactive Protein (CRP)",
        "sodium": "Sodium",
        "potassium": "Potassium",
        "chloride": "Chloride",
        "bilirubin_total": "Bilirubin Total",
        "ldh": "LDH",

        # Vitamins & Iron
        "vitamin_b12": "Vitamin B12",
        "folic_acid": "Folic Acid",
        "vitamin_d": "Vitamin D (25-OH)",
        "iron": "Iron (Sideremia)",
        "ferritin": "Ferritin",

        # Coagulation
        "prothrombin_time": "Prothrombin Time (TP)",
        "inr": "INR",
        "aptt": "aPTT",

        # Hormones & Immunology
        "tsh": "TSH",
        "free_t3": "Free T3",
        "free_t4": "Free T4",
        "hbsag": "HBsAg (Hepatitis B)",
        "anti_hbs": "Anti HBs (Hepatitis B)",
        "anti_hcv": "Anti HCV (Hepatitis C)",
        "afp": "AFP",
        "cea": "CEA",
        "psa": "PSA",
        "ca_19_9": "CA 19-9",

        # Stool Analysis
        "occult_blood": "Occult Blood",

        # Protein Electrophoresis
        "albumin_percent": "Albumin %",
        "albumin_g_dl": "Albumin (g/dL)",
        "alpha_1_percent": "Alpha-1 %",
        "alpha_1_g_dl": "Alpha-1 (g/dL)",
        "alpha_2_percent": "Alpha-2 %",
        "alpha_2_g_dl": "Alpha-2 (g/dL)",
        "beta_1_percent": "Beta-1 %",
        "beta_1_g_dl": "Beta-1 (g/dL)",
        "beta_2_percent": "Beta-2 %",
        "beta_2_g_dl": "Beta-2 (g/dL)",
        "gamma_percent": "Gamma %",
        "gamma_g_dl": "Gamma (g/dL)",
        "ag_ratio": "A/G Ratio",

        # Immunochemistry
        "igg": "Immunoglobulin G (IgG)",
        "iga": "Immunoglobulin A (IgA)",
        "igm": "Immunoglobulin M (IgM)",
        "total_ige": "Total IgE",

        # Allergy (IgE)
        "ige_lolium_perenne": "IgE Lolium perenne",
        "ige_cynodon_dactylon": "IgE Cynodon dactylon",
        "ige_phleum_pratense": "IgE Phleum pratense",
        "ige_blomia_tropicalis": "IgE Blomia tropicalis",
        "ige_dermatophagoides_farinae": "IgE Dermatophagoides farinae",
    }

    AVAILABLE_METRICS = list(METRIC_MAPPING.keys())

    def get_available_metrics(self) -> List[str]:
        return self.AVAILABLE_METRICS

    async def fetch(self, query: DataQuery) -> ChartData:
        """Fetch blood tests for the requested metric."""
        if query.metric not in self.AVAILABLE_METRICS:
            raise ValueError(
                f"Unknown blood metric '{query.metric}'. "
                f"Available metrics: {', '.join(self.AVAILABLE_METRICS)}"
            )

        # Get the exact test_name from the mapping
        test_name = self.METRIC_MAPPING[query.metric]

        start_date, end_date = self.resolve_time_range(query.time_range)

        sql = text(
            """
            SELECT
                bt.test_date,
                bt.result_value,
                bt.result_unit
            FROM blood_tests bt
            JOIN test_definitions td ON bt.test_definition_id = td.id
            WHERE td.test_name = :test_name
              AND bt.test_date BETWEEN :start_date AND :end_date
            ORDER BY bt.test_date
            LIMIT :limit
        """
        )

        session_factory = require_blood_session_factory()
        async with session_scope(session_factory) as session:
            result = await session.execute(
                sql,
                {
                    "test_name": test_name,
                    "start_date": start_date.date(),
                    "end_date": end_date.date(),
                    "limit": query.limit,
                },
            )
            rows = result.fetchall()

        labels: List[str] = []
        values: List[float] = []
        unit: str | None = None

        for row in rows:
            test_date = row.test_date
            if isinstance(test_date, datetime):
                labels.append(test_date.strftime("%Y-%m-%d"))
            else:
                labels.append(str(test_date))
            values.append(float(row.result_value) if row.result_value is not None else 0.0)
            if unit is None:
                unit = row.result_unit

        metric_label = query.metric.replace("_", " ").title()
        if unit:
            metric_label = f"{metric_label} ({unit})"

        return ChartData(labels=labels, datasets=[Dataset(label=metric_label, data=values)])


__all__ = ["BloodDataFetcher"]
