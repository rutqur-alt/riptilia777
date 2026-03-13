import logging

from fastapi import APIRouter

router = APIRouter(tags=["QR Aggregator"])
logger = logging.getLogger(__name__)
