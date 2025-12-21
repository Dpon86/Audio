"""
Common imports for all task modules.
"""
from celery import shared_task
import whisper
import difflib
import datetime
import os
import redis
from collections import defaultdict
import re
import tempfile
import logging

from django.conf import settings
from django.db import models
from django.utils import timezone
from ..models import AudioProject, AudioFile, TranscriptionSegment, TranscriptionWord
from ..services.docker_manager import docker_celery_manager
from ..utils import get_redis_connection

logger = logging.getLogger(__name__)
