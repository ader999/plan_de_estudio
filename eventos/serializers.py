from rest_framework import serializers
from django.contrib.auth.models import User
from django.utils import timezone
from .models import Evento, CriterioEvaluacion, JuradoEvento, Participante, Evaluacion


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'full_name', 'email', 'is_superuser']
        read_only_fields = ['id', 'is_superuser', 'full_name']

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username


class CriterioEvaluacionSerializer(serializers.ModelSerializer):
    class Meta:
        model = CriterioEvaluacion
        fields = ['id', 'evento', 'nombre', 'descripcion', 'puntaje_maximo']
        read_only_fields = ['id']

    def validate_puntaje_maximo(self, value):
        if value <= 0:
            raise serializers.ValidationError("El puntaje máximo debe ser un número entero mayor a 0.")
        return value


class JuradoEventoSerializer(serializers.ModelSerializer):
    usuario_detalle = UserSerializer(source='usuario', read_only=True)
    usuario_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), source='usuario', write_only=True
    )

    class Meta:
        model = JuradoEvento
        fields = ['id', 'evento', 'usuario_id', 'usuario_detalle']
        read_only_fields = ['id']


class ParticipanteSerializer(serializers.ModelSerializer):
    estado_evaluacion = serializers.SerializerMethodField(required=False)

    class Meta:
        model = Participante
        fields = ['id', 'evento', 'nombre', 'descripcion', 'integrantes', 'estado_evaluacion']
        read_only_fields = ['id']

    def get_estado_evaluacion(self, obj):
        # Si la vista ya adjuntó el estado, lo devolvemos
        if hasattr(obj, 'estado_evaluacion'):
            return obj.estado_evaluacion

        request = self.context.get('request')
        if request and request.user and request.user.is_authenticated:
            criterios_count = obj.evento.criterios.count()
            if criterios_count == 0:
                return 'Sin Criterios'
            num_evaluaciones = Evaluacion.objects.filter(
                jurado=request.user,
                participante=obj,
                criterio__evento=obj.evento
            ).count()
            if num_evaluaciones == criterios_count:
                return 'Completado'
            elif num_evaluaciones > 0:
                return 'Incompleto'
            return 'Pendiente'
        return None


class EvaluacionSerializer(serializers.ModelSerializer):
    jurado_nombre = serializers.SerializerMethodField()
    participante_nombre = serializers.ReadOnlyField(source='participante.nombre')
    criterio_nombre = serializers.ReadOnlyField(source='criterio.nombre')
    criterio_puntaje_maximo = serializers.ReadOnlyField(source='criterio.puntaje_maximo')

    class Meta:
        model = Evaluacion
        fields = [
            'id', 'jurado', 'jurado_nombre', 'participante', 'participante_nombre',
            'criterio', 'criterio_nombre', 'criterio_puntaje_maximo', 'puntaje', 'evaluado_en'
        ]
        read_only_fields = ['id', 'jurado', 'evaluado_en']

    def get_jurado_nombre(self, obj):
        return obj.jurado.get_full_name() or obj.jurado.username

    def validate(self, attrs):
        criterio = attrs.get('criterio')
        puntaje = attrs.get('puntaje')
        if criterio and puntaje is not None:
            if puntaje < 0 or puntaje > criterio.puntaje_maximo:
                raise serializers.ValidationError(
                    f"El puntaje debe estar entre 0 y {criterio.puntaje_maximo} para el criterio '{criterio.nombre}'."
                )
        return attrs


class EventoListSerializer(serializers.ModelSerializer):
    creado_por_detalle = UserSerializer(source='creado_por', read_only=True)
    esta_activo = serializers.BooleanField(read_only=True)
    ha_finalizado = serializers.BooleanField(read_only=True)
    total_criterios_score = serializers.IntegerField(read_only=True)
    participantes_count = serializers.SerializerMethodField()
    jurados_count = serializers.SerializerMethodField()
    criterios_count = serializers.SerializerMethodField()
    es_jurado = serializers.SerializerMethodField()
    es_administrador = serializers.SerializerMethodField()

    class Meta:
        model = Evento
        fields = [
            'id', 'nombre', 'descripcion', 'fecha_inicio', 'fecha_fin',
            'requiere_jurado', 'imagen', 'creado_por', 'creado_por_detalle',
            'creado_en', 'esta_activo', 'ha_finalizado', 'total_criterios_score',
            'participantes_count', 'jurados_count', 'criterios_count',
            'es_jurado', 'es_administrador'
        ]
        read_only_fields = ['id', 'creado_por', 'creado_en']

    def get_participantes_count(self, obj):
        return obj.participantes.count()

    def get_jurados_count(self, obj):
        return obj.jurados.count() if obj.requiere_jurado else 0

    def get_criterios_count(self, obj):
        return obj.criterios.count()

    def get_es_jurado(self, obj):
        request = self.context.get('request')
        if request and request.user and request.user.is_authenticated:
            return JuradoEvento.objects.filter(evento=obj, usuario=request.user).exists()
        return False

    def get_es_administrador(self, obj):
        request = self.context.get('request')
        if request and request.user and request.user.is_authenticated:
            return (obj.creado_por == request.user) or request.user.is_superuser
        return False


class EventoDetailSerializer(EventoListSerializer):
    criterios = CriterioEvaluacionSerializer(many=True, read_only=True)
    participantes = ParticipanteSerializer(many=True, read_only=True)
    jurados = JuradoEventoSerializer(many=True, read_only=True)

    class Meta(EventoListSerializer.Meta):
        fields = EventoListSerializer.Meta.fields + ['criterios', 'participantes', 'jurados']


class EventoCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Evento
        fields = [
            'id', 'nombre', 'descripcion', 'fecha_inicio', 'fecha_fin',
            'requiere_jurado', 'imagen'
        ]
        read_only_fields = ['id']

    def validate(self, attrs):
        fecha_inicio = attrs.get('fecha_inicio') or (self.instance.fecha_inicio if self.instance else None)
        fecha_fin = attrs.get('fecha_fin') or (self.instance.fecha_fin if self.instance else None)

        if fecha_inicio and fecha_fin and fecha_fin <= fecha_inicio:
            raise serializers.ValidationError({
                'fecha_fin': 'La fecha de cierre debe ser posterior a la fecha de inicio.'
            })
        return attrs


class EvaluacionItemInputSerializer(serializers.Serializer):
    criterio_id = serializers.IntegerField()
    puntaje = serializers.IntegerField(min_value=0)


class EvaluacionBulkSubmitSerializer(serializers.Serializer):
    evaluaciones = serializers.ListField(
        child=EvaluacionItemInputSerializer(),
        allow_empty=False
    )
