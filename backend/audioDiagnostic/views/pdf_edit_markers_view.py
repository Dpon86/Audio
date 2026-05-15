"""
PDF Edit Markers API
Saves and loads the structural marker configuration from the PDF Edit tab.
Keeps a rolling history of up to 20 snapshots for undo/revert.
"""
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.authentication import SessionAuthentication
from accounts.authentication import ExpiringTokenAuthentication
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from ..models import AudioProject

MAX_HISTORY = 20  # Max snapshots to keep per project


class PDFEditMarkersView(APIView):
    """
    GET  /api/projects/{id}/pdf-edit-markers/
        Returns the saved markers array and history snapshots.

    POST /api/projects/{id}/pdf-edit-markers/
        Saves a new markers array, pushing the old one into the history stack.
        Body: { "markers": [...] }

    DELETE /api/projects/{id}/pdf-edit-markers/
        Clears all markers (pushes current into history first so it can be undone).
    """
    authentication_classes = [SessionAuthentication, ExpiringTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, project_id):
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        return Response({
            'success': True,
            'markers': project.pdf_edit_markers or [],
            'history': project.pdf_edit_markers_history or [],
            'history_count': len(project.pdf_edit_markers_history or []),
        })

    def post(self, request, project_id):
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        new_markers = request.data.get('markers')

        if new_markers is None:
            return Response({'success': False, 'error': 'markers field required'}, status=status.HTTP_400_BAD_REQUEST)

        if not isinstance(new_markers, list):
            return Response({'success': False, 'error': 'markers must be an array'}, status=status.HTTP_400_BAD_REQUEST)

        # Basic validation: each marker must have id, type, audioTime
        for m in new_markers:
            if not isinstance(m, dict):
                return Response({'success': False, 'error': 'each marker must be an object'}, status=status.HTTP_400_BAD_REQUEST)
            for required in ('id', 'type', 'audioTime'):
                if required not in m:
                    return Response({'success': False, 'error': f'marker missing required field: {required}'}, status=status.HTTP_400_BAD_REQUEST)
            if not isinstance(m['audioTime'], (int, float)):
                return Response({'success': False, 'error': 'audioTime must be a number'}, status=status.HTTP_400_BAD_REQUEST)

        # Push existing markers into history (only if there are markers and they differ)
        history = list(project.pdf_edit_markers_history or [])
        current = project.pdf_edit_markers
        if current is not None and current != new_markers:
            history.append(current)
            # Trim to max
            history = history[-MAX_HISTORY:]

        project.pdf_edit_markers = new_markers
        project.pdf_edit_markers_history = history
        project.save(update_fields=['pdf_edit_markers', 'pdf_edit_markers_history'])

        return Response({
            'success': True,
            'markers': project.pdf_edit_markers,
            'history_count': len(history),
            'message': f'Saved {len(new_markers)} markers',
        })

    def delete(self, request, project_id):
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)

        # Push current into history before clearing
        history = list(project.pdf_edit_markers_history or [])
        if project.pdf_edit_markers:
            history.append(project.pdf_edit_markers)
            history = history[-MAX_HISTORY:]

        project.pdf_edit_markers = []
        project.pdf_edit_markers_history = history
        project.save(update_fields=['pdf_edit_markers', 'pdf_edit_markers_history'])

        return Response({'success': True, 'message': 'Markers cleared (previous state saved to history)'})


class PDFEditMarkersUndoView(APIView):
    """
    POST /api/projects/{id}/pdf-edit-markers/undo/
        Pops the last history snapshot and restores it as current markers.
        Returns the restored markers.
    """
    authentication_classes = [SessionAuthentication, ExpiringTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, project_id):
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        history = list(project.pdf_edit_markers_history or [])

        if not history:
            return Response({
                'success': False,
                'error': 'No history available to undo',
                'markers': project.pdf_edit_markers or [],
            }, status=status.HTTP_400_BAD_REQUEST)

        # Pop the last snapshot
        restored = history.pop()
        project.pdf_edit_markers = restored
        project.pdf_edit_markers_history = history
        project.save(update_fields=['pdf_edit_markers', 'pdf_edit_markers_history'])

        return Response({
            'success': True,
            'markers': restored,
            'history_count': len(history),
            'message': f'Restored {len(restored)} markers from history',
        })
