from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator



NUMEROS_ROMANOS = [
    ('I', 'I'),
    ('II', 'II'),
    ('III', 'III'),
    ('IV', 'IV'),
    ('V', 'V'),
    ('VI', 'VI'),
    ('VII', 'VII'),
    ('VIII', 'VIII'),
]
TRIMESTRES_ROMANOS = [
    ('I', 'I'),
    ('II', 'II'),
    ('III', 'III'),
    ('IV', 'IV'),
]



class Carrera(models.Model):
    nombre= models.CharField(max_length=100,null=False,unique=True,verbose_name='Nombre')
    def __str__(self):
        return self.nombre


class Asignatura(models.Model):
    nombre= models.CharField(max_length=100,null=False,unique=True,verbose_name='Nombre')


    def __str__(self):
        return self.nombre

class Plan_de_estudio(models.Model):
    carrera = models.ForeignKey(Carrera, on_delete=models.CASCADE)
    año = models.CharField(max_length=4, choices=NUMEROS_ROMANOS, null=False, unique=False, verbose_name='Año')
    trimestre = models.CharField(max_length=3, choices=TRIMESTRES_ROMANOS, null=False, unique=False, verbose_name='Trimestre')
    codigo = models.CharField(max_length=50, null=False, unique=True, verbose_name='Codigo')
    asignatura = models.ForeignKey('Asignatura', on_delete=models.CASCADE,null=False)
    pr = models.ForeignKey('Asignatura', null=True, blank=True, on_delete=models.CASCADE, related_name='pr_set')
    pc = models.ForeignKey('Asignatura', null=True, blank=True, on_delete=models.CASCADE, related_name='pc_set')
    cr = models.ForeignKey('Asignatura', null=True, blank=True, on_delete=models.CASCADE, related_name='cr_set')

    hp = models.IntegerField(null=False, unique=False)
    hti = models.IntegerField(null=False, unique=False)

    def __str__(self):
        return f"{self.asignatura} - {self.carrera} - {self.año}"

    def clean(self):

        if self.asignatura_id is None:
            raise ValidationError("Debes seleccionar una asignatura.")

        # Verificar si ya existe un Plan_de_estudio con la misma asignatura en la misma carrera
        existing_plans = Plan_de_estudio.objects.filter(
            carrera=self.carrera,
            asignatura=self.asignatura
        ).exclude(pk=self.pk)  # Excluir el propio objeto si se está editando
        if existing_plans.exists():
            raise ValidationError("No puedes insertar la misma asignatura en la misma carrera dos veces.")

        # Validar que los campos de horas sean mayores que cero y no estén vacíos
        if self.hp is None or not isinstance(self.hp, int) or self.hp <= 0:
            raise ValidationError("Las horas prácticas deben ser un número entero mayor que cero y no estar vacías")
        if self.hti is None or not isinstance(self.hti, int) or self.hti <= 0:
            raise ValidationError("Las horas teóricas deben ser un número entero mayor que cero y no estar vacías")


class AsignacionPlanEstudio(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    plan_de_estudio = models.ForeignKey(Plan_de_estudio, on_delete=models.CASCADE)
    plan_tematico = models.FileField(upload_to='planes_tematicos/', null=True, blank=True)
    fecha_asignacion = models.DateTimeField(auto_now_add=True)
    silabos_creados = models.IntegerField(default=0)  # Nuevo campo para contar sílabos

    class Meta:
        unique_together = ('usuario', 'plan_de_estudio')  # Asegura que un usuario no pueda tener el mismo plan dos veces

    def __str__(self):
        return f"{self.usuario} - {self.plan_de_estudio}"

    def clean(self):
        if not self.plan_de_estudio:
            raise ValidationError("Debes asignar un plan de estudio.")


class Silabo(models.Model):
    OBJETIVOS_LIST = (
        ('Conceptual', 'Conceptual'),
        ('Procedimental', 'Procedimental'),
        ('Actitudinal', 'Actitudinal'),
    )

    MOMENTOS_LIST = (
        ('Primer momento', 'Primer momento'),
        ('Segundo momento', 'Segundo momento'),
        ('Tercer momento', 'Tercer momento'),
    )

    UNIDAD_LIST = (
        ('Unidad I', 'Unidad I'),
        ('Unidad II', 'Unidad II'),
        ('Unidad III', 'Unidad III'),
        ('Unidad IV', 'Unidad IV'),
        ('Unidad V', 'Unidad V'),
        ('Unidad VI', 'Unidad VI'),
    )

    FORMA_ORGANIZATIVA_LIST = (
        ('Seminario', 'Seminario'),
        ('Conferencia', 'Conferencia'),
        ('Laboratorio', 'Laboratorio'),
        ('Talleres', 'Talleres'),
        ('Otras técnicas de aprendizaje', 'Otras técnicas de aprendizaje'),
    )

    TECNICAS_APRENDIZAJE_LIST = (
        ('Taller', 'Taller'),
        ('Trabajo de campo', 'Trabajo de campo'),
        ('Visita de campo', 'Visita de campo'),
        ('Estudio de casos', 'Estudio de casos'),
        ('Exposición', 'Exposición'),
        ('Investigación', 'Investigación'),
        ('Panel', 'Panel'),
        ('Mesa Redonda', 'Mesa Redonda'),
        ('Debate', 'Debate'),
        ('Proyecto', 'Proyecto'),
        ('Organizadores gráficos', 'Organizadores gráficos'),
        ('Ensayo', 'Ensayo'),
        ('Resumen', 'Resumen'),
        ('Video', 'Video'),
        ('Cuestionario', 'Cuestionario'),
        ('Entrevista', 'Entrevista'),
        ('Trabajo colaborativo', 'Trabajo colaborativo'),
        ('Otros', 'Otros'),
    )

    EJE_TRANSVERSAL_LIST = (
        ('Fe cristiana', 'Fe cristiana'),
        ('Proyección social', 'Proyección social'),
        ('Emprendimiento e innovación', 'Emprendimiento e innovación'),
        ('Investigación', 'Investigación'),
        ('Medio ambiente', 'Medio ambiente'),
        ('Tecnología de la información y comunicación', 'Tecnología de la información y comunicación'),
    )

    codigo = models.CharField(max_length=10)
    carrera = models.ForeignKey(Carrera, on_delete=models.CASCADE, verbose_name='Carrera')
    asignatura = models.ForeignKey(Plan_de_estudio, on_delete=models.CASCADE, verbose_name='Pla de estudio')
    maestro = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='Maestro')

    encuentros = models.IntegerField( validators=[MinValueValidator(1), MaxValueValidator(12)])
    fecha = models.DateField(verbose_name='Fecha')

    objetivo_conceptual = models.TextField(verbose_name='Objetivo Conceptual', blank=False)
    objetivo_procedimental = models.TextField(verbose_name='Objetivo Procedimental', blank=False)
    objetivo_actitudinal = models.TextField(verbose_name='Objetivo Actitudinal', blank=False)

    momento_didactico_primer = models.TextField(verbose_name='Primer Momento Didáctico', blank=False)
    momento_didactico_segundo = models.TextField(verbose_name='Segundo Momento Didáctico', blank=False)
    momento_didactico_tercer = models.TextField(verbose_name='Tercer Momento Didáctico', blank=False)

    unidad = models.CharField(max_length=255,choices=UNIDAD_LIST)
    detalle_unidad = models.CharField(max_length=555)
    contenido_tematico = models.TextField(max_length=555)
    forma_organizativa = models.CharField(max_length=255, choices=FORMA_ORGANIZATIVA_LIST)
    tiempo = models.CharField(max_length=10)
    tecnicas_aprendizaje = models.CharField(max_length=255, choices=TECNICAS_APRENDIZAJE_LIST)
    descripcion_estrategia = models.TextField(max_length=555)
    eje_transversal = models.CharField(max_length=255,choices=EJE_TRANSVERSAL_LIST)
    hp = models.CharField(max_length=10)
    guia = models.ForeignKey('Guia', on_delete=models.CASCADE, verbose_name="Guía de estudio", null=True, blank=True, related_name="silabos")
    asignacion_plan = models.ForeignKey(AsignacionPlanEstudio, on_delete=models.CASCADE, null=True, blank=True,
                                         related_name="silabo_set")

    def __str__(self):
        return f'Silabo {self.id}'


class PlanTematico(models.Model):
    nombre_de_la_unidad = models.IntegerField()
    clases_teoricas_s = models.IntegerField()
    clases_teoricas_c = models.IntegerField()
    tct = models.IntegerField()
    clases_practicas_laboratorio = models.IntegerField()
    clases_practicas_campo_trabajo = models.IntegerField()
    clases_practicas_teoria = models.IntegerField()
    clases_practicas_visitas_tc = models.IntegerField()
    tcp = models.IntegerField()
    evaluacion_final_examen = models.IntegerField()
    evaluacion_final_trabajo_clase = models.IntegerField()
    evaluacion_final_participacion_clase = models.IntegerField()
    te = models.IntegerField()  # Total de evaluaciones
    thp = models.IntegerField() # Total de horas prácticas
    ti = models.IntegerField()  # Total de intervenciones
    th = models.IntegerField()  # Total de horas

    def __str__(self):
        return f'Unidad: {self.nombre_de_la_unidad} (ID: {self.id})'

class Unidades(models.Model):
    objetivo_especifico = models.CharField(max_length=555)
    objetivo_procedimental = models.CharField(max_length=555)
    objetivo_actitudinal = models.CharField(max_length=555)
    plan_analitico = models.CharField(max_length=555)
    recomendaciones_metodologicas = models.CharField(max_length=800)
    forma_de_evaluacion = models.CharField(max_length=800)
    relacion_eje_contenido_de_la_unidad = models.CharField(max_length=800)
    plan_tematico = models.ForeignKey(PlanTematico, on_delete=models.CASCADE, related_name='unidades')

    def __str__(self):
        return f'Objetivo de la Unidad: {self.objetivo_especifico} (Plan Temático: {self.plan_tematico.nombre_de_la_unidad})'


class Guia(models.Model):
    """
    Representa una guía de estudio dentro del sílabo.
    """
    TIPO_OBJETIVO_CHOICES = [
        ('Conceptual', 'Conceptual'),
        ('Procedimental', 'Procedimental'),
        ('Actitudinal', 'Actitudinal'),
    ]
    
    silabo = models.ForeignKey(Silabo, on_delete=models.CASCADE, related_name="guias")
    numero_guia = models.IntegerField(verbose_name="N° Guía")
    fecha = models.DateField()
    unidad = models.CharField(max_length=255, choices=Silabo.UNIDAD_LIST, verbose_name="N° de unidad")
    objetivo = models.CharField(max_length=20, choices=TIPO_OBJETIVO_CHOICES, verbose_name="Objetivo")
    contenido_tematico = models.TextField(blank=True, null=True, verbose_name="Contenido Temático")
    actividades = models.TextField(blank=True, null=True, verbose_name="Actividades")
    instrumento_evaluacion = models.TextField(blank=True, null=True, verbose_name="Instrumento de evaluación")
    criterios_evaluacion = models.TextField(blank=True, null=True, verbose_name="Criterios de evaluación")
    tiempo_minutos = models.FloatField(blank=True, null=True, verbose_name="Tiempo en minutos")
    recursos = models.TextField(blank=True, null=True, verbose_name="Recursos")
    puntaje = models.FloatField(blank=True, null=True, verbose_name="Puntaje")
    evaluacion_sumativa = models.CharField(max_length=255, blank=True, null=True, verbose_name="Evaluación sumativa")
    fecha_entrega = models.DateField(blank=True, null=True, verbose_name="Fecha de Entrega")
    
    def __str__(self):
        return f"Guía {self.numero_guia} - {self.unidad} - {self.fecha}"
