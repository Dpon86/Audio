"""
Common imports for all view modules.
"""
import os
import json
import redis
import datetime
import tempfile
import logging
import io

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.decorators import authentication_classes, permission_classes
from rest_framework.authentication import SessionAuthentication, BasicAuthentication, TokenAuthentication
from rest_framework.permissions import IsAuthenticated

from django.http import JsonResponse, FileResponse, Http404, HttpResponseBadRequest
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404

from ..serializers import (
    AudioProjectSerializer, ProjectCreateSerializer, AudioFileSerializer,
    PDFUploadSerializer, AudioUploadSerializer, DuplicateConfirmationSerializer
)
from ..throttles import UploadRateThrottle, TranscribeRateThrottle, ProcessRateThrottle
from ..models import AudioProject, AudioFile, TranscriptionSegment, TranscriptionWord

from celery.result import AsyncResult

logger = logging.getLogger(__name__)
