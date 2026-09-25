from rest_framework import status, views, viewsets
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q, Sum, Avg

from .models import Evento, CriterioEvaluacion, JuradoEvento, Participante, Evaluacion
from .serializers import (
    UserSerializer,
    EventoListSerializer,
    EventoDetailSerializer,
    EventoCreateUpdateSerializer,
    CriterioEvaluacionSerializer,
    JuradoEventoSerializer,
    ParticipanteSerializer,
    EvaluacionSerializer,
    EvaluacionBulkSubmitSerializer,
)
from .permissions import IsEventoCreatorOrAdmin


# ============================================================================
# AUTENTICACIÓN
# ============================================================================

@api_view(['POST'])
@permission_classes([AllowAny])
def api_login(request):
    """
    Inicia sesión con username y password.
    Retorna el Token DRF y la información del usuario autenticado.
    """
    username = request.data.get('username')
    password = request.data.get('password')

    if not username or not password:
        return Response(
            {'detail': 'Se requieren el nombre de usuario y la contraseña.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    user = authenticate(request, username=username, password=password)
    if not user:
        return Response(
            {'detail': 'Credenciales inválidas. Por favor verifica usuario y contraseña.'},
            status=status.HTTP_401_UNAUTHORIZED
        )

    token, _ = Token.objects.get_or_create(user=user)
    login(request, user)  # También mantiene sesión de Django si se usa cookies

    return Response({
        'token': token.key,
        'user': UserSerializer(user).data,
        'detail': f'Bienvenido {user.get_full_name() or user.username}'
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_logout(request):
    """
    Cierra sesión y elimina el Token de autenticación del usuario.
    """
    try:
        request.user.auth_token.delete()
    except Exception:
        pass
    logout(request)
    return Response({'detail': 'Sesión cerrada correctamente.'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_me(request):
    """
    Obtiene los datos del usuario actualmente autenticado.
    """
    return Response(UserSerializer(request.user).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_usuarios_disponibles(request, evento_id=None):
    """
    Lista de usuarios disponibles en el sistema.
    Si se proporciona evento_id, excluye los usuarios que ya son jurados de dicho evento.
    """
    queryset = User.objects.all()
    if evento_id:
        evento = get_object_or_404(Evento, id=evento_id)
        jurados_ids = evento.jurados.values_list('usuario_id', flat=True)
        queryset = queryset.exclude(id__in=jurados_ids)
    
    queryset = queryset.order_by('first_name', 'username')
    return Response(UserSerializer(queryset, many=True).data)


# ============================================================================
# EVENTOS VIEWSET
# ============================================================================

class EventoViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsEventoCreatorOrAdmin]

    def get_permissions(self):
        # Para evaluar o ver resultados, la verificación de jurado o finalización se hace dentro de la acción
        if self.action in ['evaluar_lista', 'evaluar_proyecto', 'resultados']:
            return [IsAuthenticated()]
        return [IsAuthenticated(), IsEventoCreatorOrAdmin()]

    def get_queryset(self):
        ahora = timezone.now()
        queryset = Evento.objects.all().select_related('creado_por').prefetch_related(
            'criterios', 'participantes', 'jurados__usuario'
        )

        # Filtro por estado
        estado = self.request.query_params.get('status')
        if estado == 'activos':
            queryset = queryset.filter(fecha_inicio__lte=ahora, fecha_fin__gte=ahora)
        elif estado == 'proximos':
            queryset = queryset.filter(fecha_inicio__gt=ahora)
        elif estado == 'finalizados':
            queryset = queryset.filter(fecha_fin__lt=ahora)

        # Búsqueda por texto
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(nombre__icontains=search) | Q(descripcion__icontains=search)
            )

        return queryset

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return EventoDetailSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return EventoCreateUpdateSerializer
        return EventoListSerializer

    def perform_create(self, serializer):
        serializer.save(creado_por=self.request.user)

    # ------------------------------------------------------------------------
    # CRITERIOS DE UN EVENTO
    # ------------------------------------------------------------------------
    @action(detail=True, methods=['get', 'post'], url_path='criterios')
    def criterios(self, request, pk=None):
        evento = self.get_object()

        if request.method == 'GET':
            criterios = evento.criterios.all()
            return Response(CriterioEvaluacionSerializer(criterios, many=True).data)

        # POST: Crear nuevo criterio
        if evento.creado_por != request.user and not request.user.is_superuser:
            return Response(
                {'detail': 'No tienes permisos para agregar criterios a este evento.'},
                status=status.HTTP_403_FORBIDDEN
            )

        data = request.data.copy()
        data['evento'] = evento.id
        serializer = CriterioEvaluacionSerializer(data=data)
        if serializer.is_valid():
            criterio = serializer.save()
            return Response(CriterioEvaluacionSerializer(criterio).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # ------------------------------------------------------------------------
    # PARTICIPANTES DE UN EVENTO
    # ------------------------------------------------------------------------
    @action(detail=True, methods=['get', 'post'], url_path='participantes')
    def participantes(self, request, pk=None):
        evento = self.get_object()

        if request.method == 'GET':
            participantes = evento.participantes.all()
            context = {'request': request}
            return Response(ParticipanteSerializer(participantes, many=True, context=context).data)

        # POST: Crear nuevo participante
        if evento.creado_por != request.user and not request.user.is_superuser:
            return Response(
                {'detail': 'No tienes permisos para agregar participantes a este evento.'},
                status=status.HTTP_403_FORBIDDEN
            )

        data = request.data.copy()
        data['evento'] = evento.id
        serializer = ParticipanteSerializer(data=data, context={'request': request})
        if serializer.is_valid():
            participante = serializer.save()
            return Response(ParticipanteSerializer(participante, context={'request': request}).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # ------------------------------------------------------------------------
    # JURADOS DE UN EVENTO
    # ------------------------------------------------------------------------
    @action(detail=True, methods=['get', 'post'], url_path='jurados')
    def jurados(self, request, pk=None):
        evento = self.get_object()

        if request.method == 'GET':
            jurados = evento.jurados.all()
            jurados_user_ids = jurados.values_list('usuario_id', flat=True)
            usuarios_disponibles = User.objects.exclude(id__in=jurados_user_ids).order_by('first_name', 'username')

            return Response({
                'jurados': JuradoEventoSerializer(jurados, many=True).data,
                'usuarios_disponibles': UserSerializer(usuarios_disponibles, many=True).data,
                'requiere_jurado': evento.requiere_jurado
            })

        # POST: Asignar nuevo jurado
        if not evento.requiere_jurado:
            return Response(
                {'detail': 'Este evento está configurado para no requerir jurado.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if evento.creado_por != request.user and not request.user.is_superuser:
            return Response(
                {'detail': 'No tienes permisos para gestionar el jurado de este evento.'},
                status=status.HTTP_403_FORBIDDEN
            )

        usuario_id = request.data.get('usuario_id')
        if not usuario_id:
            return Response(
                {'detail': 'Debes especificar usuario_id.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        usuario = get_object_or_404(User, id=usuario_id)
        jurado_obj, created = JuradoEvento.objects.get_or_create(evento=evento, usuario=usuario)
        status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(JuradoEventoSerializer(jurado_obj).data, status=status_code)

    # ------------------------------------------------------------------------
    # EVALUACIÓN (LISTA DE EQUIPOS A EVALUAR)
    # ------------------------------------------------------------------------
    @action(detail=True, methods=['get'], url_path='evaluar')
    def evaluar_lista(self, request, pk=None):
        evento = self.get_object()
        es_jurado = JuradoEvento.objects.filter(evento=evento, usuario=request.user).exists()

        if not es_jurado and not request.user.is_superuser:
            return Response(
                {'detail': 'No estás registrado como jurado de este evento.'},
                status=status.HTTP_403_FORBIDDEN
            )

        ahora = timezone.now()
        if ahora < evento.fecha_inicio:
            return Response(
                {'detail': 'El evento aún no ha iniciado.', 'codigo': 'EVENTO_NO_INICIADO'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if ahora > evento.fecha_fin:
            return Response(
                {'detail': 'El evento ya ha finalizado, no se permiten más evaluaciones.', 'codigo': 'EVENTO_FINALIZADO'},
                status=status.HTTP_400_BAD_REQUEST
            )

        criterios = evento.criterios.all()
        if not criterios.exists():
            return Response(
                {'detail': 'Este evento no tiene criterios de evaluación definidos.', 'codigo': 'SIN_CRITERIOS'},
                status=status.HTTP_400_BAD_REQUEST
            )

        participantes = evento.participantes.all()
        participantes_data = []

        for p in participantes:
            evaluaciones = Evaluacion.objects.filter(
                jurado=request.user,
                participante=p,
                criterio__evento=evento
            )
            count = evaluaciones.count()
            if count == criterios.count() and criterios.count() > 0:
                estado_eval = 'Completado'
            elif count > 0:
                estado_eval = 'Incompleto'
            else:
                estado_eval = 'Pendiente'

            participantes_data.append({
                'id': p.id,
                'nombre': p.nombre,
                'descripcion': p.descripcion,
                'integrantes': p.integrantes,
                'estado_evaluacion': estado_eval,
                'criterios_evaluados': count,
                'total_criterios': criterios.count(),
            })

        return Response({
            'evento_id': evento.id,
            'evento_nombre': evento.nombre,
            'participantes': participantes_data,
            'total_participantes': len(participantes_data),
        })

    # ------------------------------------------------------------------------
    # EVALUAR PROYECTO ESPECÍFICO (GET DETALLES & POST CALIFICACIONES)
    # ------------------------------------------------------------------------
    @action(detail=True, methods=['get', 'post'], url_path=r'evaluar/(?P<participante_id>\d+)')
    def evaluar_proyecto(self, request, pk=None, participante_id=None):
        evento = self.get_object()
        participante = get_object_or_404(Participante, id=participante_id, evento=evento)

        es_jurado = JuradoEvento.objects.filter(evento=evento, usuario=request.user).exists()
        if not es_jurado and not request.user.is_superuser:
            return Response(
                {'detail': 'No estás registrado como jurado de este evento.'},
                status=status.HTTP_403_FORBIDDEN
            )

        ahora = timezone.now()
        if ahora < evento.fecha_inicio or ahora > evento.fecha_fin:
            return Response(
                {'detail': 'Las evaluaciones están cerradas para este evento.', 'codigo': 'EVALUACION_CERRADA'},
                status=status.HTTP_400_BAD_REQUEST
            )

        criterios = evento.criterios.all()
        if not criterios.exists():
            return Response(
                {'detail': 'El evento no tiene criterios definidos.', 'codigo': 'SIN_CRITERIOS'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # GET: Retorna los criterios y calificaciones previas del jurado
        if request.method == 'GET':
            evaluaciones_previas = Evaluacion.objects.filter(jurado=request.user, participante=participante)
            calificaciones_map = {ev.criterio_id: ev.puntaje for ev in evaluaciones_previas}

            criterios_list = []
            for c in criterios:
                criterios_list.append({
                    'id': c.id,
                    'nombre': c.nombre,
                    'descripcion': c.descripcion,
                    'puntaje_maximo': c.puntaje_maximo,
                    'puntaje_actual': calificaciones_map.get(c.id, None)
                })

            total_asignado = sum(val for val in calificaciones_map.values() if val is not None)

            return Response({
                'evento_id': evento.id,
                'evento_nombre': evento.nombre,
                'participante': ParticipanteSerializer(participante).data,
                'criterios': criterios_list,
                'total_criterios_score': evento.total_criterios_score,
                'total_asignado': total_asignado,
            })

        # POST: Guardar o actualizar calificaciones
        # Soporta dos formatos:
        # Formato 1: {"evaluaciones": [{"criterio_id": 1, "puntaje": 10}, ...]}
        # Formato 2: {"criterio_1": 10, "criterio_2": 20, ...}
        calificaciones_data = {}
        if 'evaluaciones' in request.data and isinstance(request.data['evaluaciones'], list):
            for item in request.data['evaluaciones']:
                cid = item.get('criterio_id')
                puntaje = item.get('puntaje')
                if cid is not None and puntaje is not None:
                    calificaciones_data[int(cid)] = int(puntaje)
        else:
            for c in criterios:
                key = f'criterio_{c.id}'
                if key in request.data:
                    try:
                        calificaciones_data[c.id] = int(request.data[key])
                    except (ValueError, TypeError):
                        pass
                elif str(c.id) in request.data:
                    try:
                        calificaciones_data[c.id] = int(request.data[str(c.id)])
                    except (ValueError, TypeError):
                        pass

        # Validaciones de criterios y rangos
        errores = {}
        for c in criterios:
            if c.id not in calificaciones_data:
                errores[f'criterio_{c.id}'] = f"Falta el puntaje para el criterio '{c.nombre}'."
            else:
                pts = calificaciones_data[c.id]
                if pts < 0 or pts > c.puntaje_maximo:
                    errores[f'criterio_{c.id}'] = f"El puntaje debe ser entre 0 y {c.puntaje_maximo}."

        if errores:
            return Response({'detail': 'Errores de validación', 'errors': errores}, status=status.HTTP_400_BAD_REQUEST)

        # Guardar / actualizar en la base de datos
        evaluaciones_guardadas = []
        for c in criterios:
            pts = calificaciones_data[c.id]
            eval_obj, _ = Evaluacion.objects.update_or_create(
                jurado=request.user,
                participante=participante,
                criterio=c,
                defaults={'puntaje': pts}
            )
            evaluaciones_guardadas.append(eval_obj)

        return Response({
            'detail': f"Evaluación guardada exitosamente para '{participante.nombre}'.",
            'participante_id': participante.id,
            'evaluaciones': EvaluacionSerializer(evaluaciones_guardadas, many=True).data
        }, status=status.HTTP_200_OK)

    # ------------------------------------------------------------------------
    # RESULTADOS / TABLA DE POSICIONES / CUADRO DE HONOR
    # ------------------------------------------------------------------------
    @action(detail=True, methods=['get'], url_path='resultados')
    def resultados(self, request, pk=None):
        evento = self.get_object()
        ahora = timezone.now()

        es_administrador = (evento.creado_por == request.user) or request.user.is_superuser
        es_previsualizacion = ahora <= evento.fecha_fin

        if es_previsualizacion and not es_administrador:
            return Response(
                {
                    'detail': f"Los resultados estarán disponibles públicamente una vez que finalice el evento (después de {evento.fecha_fin}).",
                    'codigo': 'RESULTADOS_NO_PUBLICOS',
                    'fecha_fin': evento.fecha_fin
                },
                status=status.HTTP_403_FORBIDDEN
            )

        participantes = evento.participantes.all()
        criterios = evento.criterios.all()

        resultados_list = []
        for participante in participantes:
            evaluaciones = Evaluacion.objects.filter(participante=participante)
            jurados_evaluadores = evaluaciones.values('jurado').annotate(total_score=Sum('puntaje'))

            scores_list = [item['total_score'] for item in jurados_evaluadores]
            promedio_final = sum(scores_list) / len(scores_list) if scores_list else 0.0

            desglose_criterios = {}
            for criterio in criterios:
                promedio_criterio = evaluaciones.filter(criterio=criterio).aggregate(Avg('puntaje'))['puntaje__avg'] or 0.0
                desglose_criterios[criterio.id] = round(float(promedio_criterio), 2)

            resultados_list.append({
                'participante': ParticipanteSerializer(participante).data,
                'puntaje_promedio': round(float(promedio_final), 2),
                'evaluadores_count': len(scores_list),
                'desglose_criterios': desglose_criterios
            })

        # Ordenar por puntaje_promedio descendente
        resultados_list = sorted(resultados_list, key=lambda x: x['puntaje_promedio'], reverse=True)

        for i, res in enumerate(resultados_list):
            res['puesto'] = i + 1

        podio = {
            'primero': resultados_list[0] if len(resultados_list) >= 1 else None,
            'segundo': resultados_list[1] if len(resultados_list) >= 2 else None,
            'tercero': resultados_list[2] if len(resultados_list) >= 3 else None,
        }

        return Response({
            'evento': EventoListSerializer(evento, context={'request': request}).data,
            'criterios': CriterioEvaluacionSerializer(criterios, many=True).data,
            'podio': podio,
            'resultados': resultados_list,
            'es_previsualizacion': es_previsualizacion,
            'total_participantes': len(resultados_list)
        })


# ============================================================================
# GESTIÓN INDIVIDUAL DE CRITERIOS, PARTICIPANTES Y JURADOS
# ============================================================================

@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def api_criterio_detail(request, criterio_id):
    criterio = get_object_or_404(CriterioEvaluacion, id=criterio_id)
    evento = criterio.evento

    if request.method == 'GET':
        return Response(CriterioEvaluacionSerializer(criterio).data)

    if evento.creado_por != request.user and not request.user.is_superuser:
        return Response({'detail': 'No tienes permisos para modificar este criterio.'}, status=status.HTTP_403_FORBIDDEN)

    if request.method == 'DELETE':
        criterio.delete()
        return Response({'detail': 'Criterio eliminado con éxito.'}, status=status.HTTP_200_OK)

    serializer = CriterioEvaluacionSerializer(criterio, data=request.data, partial=(request.method == 'PATCH'))
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def api_participante_detail(request, participante_id):
    participante = get_object_or_404(Participante, id=participante_id)
    evento = participante.evento

    if request.method == 'GET':
        return Response(ParticipanteSerializer(participante, context={'request': request}).data)

    if evento.creado_por != request.user and not request.user.is_superuser:
        return Response({'detail': 'No tienes permisos para modificar este participante.'}, status=status.HTTP_403_FORBIDDEN)

    if request.method == 'DELETE':
        participante.delete()
        return Response({'detail': 'Participante eliminado con éxito.'}, status=status.HTTP_200_OK)

    serializer = ParticipanteSerializer(participante, data=request.data, partial=(request.method == 'PATCH'), context={'request': request})
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def api_jurado_detail(request, jurado_id):
    jurado = get_object_or_404(JuradoEvento, id=jurado_id)
    evento = jurado.evento

    if evento.creado_por != request.user and not request.user.is_superuser:
        return Response({'detail': 'No tienes permisos para remover jurados de este evento.'}, status=status.HTTP_403_FORBIDDEN)

    nombre = jurado.usuario.get_full_name() or jurado.usuario.username
    jurado.delete()
    return Response({'detail': f"{nombre} ha sido removido del jurado."}, status=status.HTTP_200_OK)
