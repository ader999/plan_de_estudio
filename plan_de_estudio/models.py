from threading import Condition
from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models.functions.text import CharField
from django.utils.regex_helper import Choice
from multiselectfield import MultiSelectField




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
    formaciones = [
        ('Educación', 'Educación'),
        ('Artes y Humanidades', 'Artes y Humanidades'),
        ('Ciencias Sociales, Periodismo e información', 'Ciencias Sociales, Periodismo e información'),
        ('Administración de empresas y derecho', 'Administración de empresas y derecho'),
        ('Tecnologías de la información', 'Tecnologías de la información'),
        ('Agricultura', 'Agricultura'),
        ('Salud y servicios sociales ', 'Salud y servicios sociales ')
    ]

    nombre= models.CharField(max_length=100,null=False,unique=True,verbose_name='Nombre de la carrera')
    codigo = models.CharField(max_length=50, null=False, unique=True, verbose_name='Codigo')
    cine_2011 = models.IntegerField(null=False, verbose_name="A.C. CINE 2011")
    cine_2013 = models.IntegerField(null=False, verbose_name="A.C. CINE 2013")
    area_formacion = models.CharField(max_length=100 ,choices=formaciones, verbose_name="Área de formación")
    area_disiplinaria = models.IntegerField(null=False, verbose_name="Área disciplinaria")


    def __str__(self):
        return self.nombre


class Asignatura(models.Model):
    nombre= models.CharField(max_length=100,null=False,unique=True,verbose_name='Nombre')


    def __str__(self):
        return self.nombre.upper()

    def clean(self):
        if self.nombre:
            if Asignatura.objects.filter(nombre__iexact=self.nombre).exclude(pk=self.pk).exists():
                raise ValidationError({'nombre': 'La asignatura con este nombre ya existe.'})

class Plan_de_estudio(models.Model):
    carrera = models.ForeignKey(Carrera, on_delete=models.CASCADE)
    año = models.CharField(max_length=4, choices=NUMEROS_ROMANOS, null=False, unique=False, verbose_name='Año')
    trimestre = models.CharField(max_length=3, choices=TRIMESTRES_ROMANOS, null=False, unique=False, verbose_name='Trimestre')
    codigo = models.CharField(max_length=50, null=False, unique=True, verbose_name='Codigo')
    asignatura = models.ForeignKey('Asignatura', on_delete=models.CASCADE,null=False)
    pr = models.ForeignKey('Asignatura', null=True, blank=True, on_delete=models.CASCADE, related_name='pr_set')
    pc = models.ForeignKey('Asignatura', null=True, blank=True, on_delete=models.CASCADE, related_name='pc_set')
    cr = models.ForeignKey('Asignatura', null=True, blank=True, on_delete=models.CASCADE, related_name='cr_set')
    plan_tematico = models.FileField(upload_to='planes_tematicos/', null=True, blank=True)
    plan_tematico_ref = models.ForeignKey('PlanTematico', on_delete=models.CASCADE, verbose_name='Plan temático relacionado', related_name='planes_de_estudio', null=True, blank=True)
    documento_adjunto = models.FileField(upload_to='documentos_plan_estudio/', null=True, blank=True, verbose_name='Documento adjunto')


    horas_presenciales = models.IntegerField(null=False, unique=False, verbose_name="Horas presenciales", validators=[MinValueValidator(1)])
    horas_estudio_independiente = models.IntegerField(null=False, unique=False, verbose_name="Horas de estudio independiente", validators=[MinValueValidator(1)])

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
        if self.horas_presenciales is None or not isinstance(self.horas_presenciales, int) or self.horas_presenciales <= 0:
            raise ValidationError("Las horas **presenciales** deben ser un número entero mayor que cero y no estar vacías")

        if self.horas_estudio_independiente is None or not isinstance(self.horas_estudio_independiente, int) or self.horas_estudio_independiente <= 0:
            raise ValidationError("Las horas de estudio independiente deben ser un número entero mayor que cero y no estar vacías")


        # Validación para plan_tematico_ref
        if self.plan_tematico_ref:
            # Verificar si este plan temático ya está asignado a otro plan de estudio
            existing_assignment = Plan_de_estudio.objects.filter(
                plan_tematico_ref=self.plan_tematico_ref
            ).exclude(pk=self.pk).exists()

            if existing_assignment:
                raise ValidationError("Este plan temático ya está asignado a otro plan de estudio.")

    def get_plan_tematico_efectivo(self):
        """
        Devuelve el PlanTematico asociado, ya sea por la relación directa (plan_tematico_ref)
        o por la relación inversa (plantematicos_asociados).
        Priotiza la relación directa.
        """
        if self.plan_tematico_ref:
            return self.plan_tematico_ref
        
        # Verificar relación inversa
        asociado = self.plantematicos_asociados.first()
        if asociado:
            return asociado
            
        return None


class AsignacionPlanEstudio(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    plan_de_estudio = models.ForeignKey(Plan_de_estudio, on_delete=models.CASCADE)
    fecha_asignacion = models.DateTimeField(auto_now_add=True)
    silabos_creados = models.IntegerField(default=0)
    guias_creadas = models.IntegerField(default=0)

    class Meta:
        unique_together = ('usuario', 'plan_de_estudio')

    def __str__(self):
        return f"{self.usuario} - {self.plan_de_estudio}"

    def clean(self):
        if not self.plan_de_estudio:
            raise ValidationError("Debes asignar un plan de estudio.")


class Silabo(models.Model):
    UNIDAD_LIST = (
        ('Unidad I', 'Unidad I'),
        ('Unidad II', 'Unidad II'),
        ('Unidad III', 'Unidad III'),
        ('Unidad IV', 'Unidad IV'),
        ('Unidad V', 'Unidad V'),
        ('Unidad VI', 'Unidad VI'),
    )

    EJE_TRANSVERSAL_LIST = (
        ('Proyección social', 'Proyección social'),
        ('Emprendimiento e innovación', 'Emprendimiento e innovación'),
        ('Investigación', 'Investigación'),
        ('Medio ambiente', 'Medio ambiente'),
        ('Tecnología de la información y comunicación', 'Tecnología de la información y comunicación'),
        ('Cultura de paz', 'Cultura de paz'),
        ('Interculturalidad', 'Interculturalidad'),
        ('Internacionalización', 'Internacionalización'),
        ('Competencias para la vida', 'Competencias para la vida'),
        ('Fe cristiana', 'Fe cristiana'),
    )

    MODALIDAD_LIST = (
        ('Presencial', 'Presencial'),
        ('Virtual', 'Virtual'),
        ('Híbrida', 'Híbrida'),
    )

    TECNICA_EVALUACION_LIST = (
        ('Observación', 'Observación'),
        ('Preguntas', 'Preguntas'),
        ('Debate', 'Debate'),
        ('Trabajo en grupo', 'Trabajo en grupo'),
        ('Presentación oral', 'Presentación oral'),
        ('Ensayo', 'Ensayo'),
        ('Proyecto', 'Proyecto'),
        ('Organizador gráfico', 'Organizador gráfico'),
        ('Otro', 'Otro'),
    )

    TIPO_EVALUACION_LIST = (
        ('Diagnóstica', 'Diagnóstica'),
        ('Formativa', 'Formativa'),
        ('Sumativa', 'Sumativa'),
    )

    PERIODO_TIEMPO_LIST = (
        ('I Corte Evaluativo', 'I Corte Evaluativo'),
        ('II Corte Evaluativo', 'II Corte Evaluativo'),
        ('III Corte Evaluativo', 'III Corte Evaluativo'),
    )

    AGENTE_EVALUADOR_LIST = (
        ('Autoevaluación', 'Autoevaluación'),
        ('Coevaluación', 'Coevaluación'),
        ('Heteroevaluación', 'Heteroevaluación'),
    )

    INSTRUMENTO_EVALUACION_LIST = (
        ('Rúbrica', 'Rúbrica'),
        ('Listas de cotejo', 'Listas de cotejo'),
        ('Prueba oral', 'Prueba oral'),
        ('Prueba escrita', 'Prueba escrita'),
        ('Registro anecdótico', 'Registro anecdótico'),
        ('Diario de aprendizaje', 'Diario de aprendizaje'),
        ('Portafolio', 'Portafolio'),
        ('Cuaderno del estudiante', 'Cuaderno del estudiante'),
        ('Escalas de valoración', 'Escalas de valoración'),
        ('Otros', 'Otros'),
    )

    TIPO_PRIMER_MOMENTO_LIST = (
        ('Evaluación diagnóstica', 'Evaluación diagnóstica'),
        ('Presentación de asignatura', 'Presentación de asignatura'),
        ('Presentación del grupo', 'Presentación del grupo'),
        ('Valoración del trabajo independiente', 'Valoración del trabajo independiente'),
        ('Realimentación del aprendizaje', 'Realimentación del aprendizaje'),
        ('Autoevaluación', 'Autoevaluación'),
        ('Coevaluación', 'Coevaluación'),
    )

    TIPO_SEGUNDO_MOMENTO_TEORIA_LIST = (
        ('Conferencia', 'Conferencia'),
        ('Seminario', 'Seminario'),
        ('Evaluación formativa', 'Evaluación formativa'),
        ('Autoevaluación', 'Autoevaluación'),
        ('Coevaluación', 'Coevaluación'),
        ('Realimentación del aprendizaje', 'Realimentación del aprendizaje'),
        ('Adecuación curricular', 'Adecuación curricular'),
    )

    TIPO_SEGUNDO_MOMENTO_PRACTICA_LIST = (
        ('Laboratorio', 'Laboratorio'),
        ('Taller', 'Taller'),
        ('Evaluación formativa', 'Evaluación formativa'),
        ('Autoevaluación', 'Autoevaluación'),
        ('Coevaluación', 'Coevaluación'),
        ('Realimentación del aprendizaje', 'Realimentación del aprendizaje'),
    )

    TIPO_TERCER_MOMENTO_LIST = (
        ('Orientación del estudio independiente', 'Orientación del estudio independiente'),
        ('Realimentación del aprendizaje', 'Realimentación del aprendizaje'),
    )

    # Datos existentes (mantener)
    codigo = models.CharField(max_length=20)

    # Sección 1: Información general del plan de estudio (según imagen 1)
    encuentros = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(12)])
    fecha = models.DateField(verbose_name='Fecha')
    unidad = models.CharField(max_length=255, choices=UNIDAD_LIST)
    nombre_de_la_unidad = models.CharField(max_length=255, verbose_name='Nombre de la unidad')
    contenido_tematico = models.TextField(verbose_name='Contenido temático')

    # Sección 2: Objetivos de la unidad (según imagen 1)
    objetivo_conceptual = models.TextField(verbose_name='Objetivo Conceptual', blank=False)
    objetivo_procedimental = models.TextField(verbose_name='Objetivo Procedimental', blank=False)
    objetivo_actitudinal = models.TextField(verbose_name='Objetivo Actitudinal', blank=False)

    # Sección 3: Descripción de las fases del acto mental (según imagen 2)
    # Primer momento didáctico (fase entrada)
    tipo_primer_momento = models.CharField(max_length=100, choices=TIPO_PRIMER_MOMENTO_LIST, verbose_name='Tipo enseñanza primer momento')
    detalle_primer_momento = models.TextField(verbose_name='Detalle enseñanza primer momento')
    tiempo_primer_momento = models.IntegerField(verbose_name='Tiempo primer momento (minutos)', validators=[MinValueValidator(1)])
    recursos_primer_momento = models.TextField(verbose_name='Recursos didácticos primer momento')

    # Segundo momento didáctico (fase elaboración)
    tipo_segundo_momento_claseteoria = models.CharField(max_length=100, choices=TIPO_SEGUNDO_MOMENTO_TEORIA_LIST, verbose_name='Tipo enseñanza clase teórica')
    clase_teorica = models.TextField(verbose_name='Clase teórica')
    tipo_segundo_momento_practica = models.CharField(max_length=100, choices=TIPO_SEGUNDO_MOMENTO_PRACTICA_LIST, verbose_name='Tipo enseñanza clase práctica')
    clase_practica = models.TextField(verbose_name='Clase práctica')
    tiempo_segundo_momento_teorica = models.IntegerField(verbose_name='Tiempo clase teorica (minutos)', validators=[MinValueValidator(1)])
    tiempo_segundo_momento_practica = models.IntegerField(verbose_name='Tiempo segundo practica (minutos)', validators=[MinValueValidator(1)],)
    recursos_segundo_momento = models.TextField(verbose_name='Recursos didácticos segundo momento')

    # Tercer momento didáctico (fase salida)
    tipo_tercer_momento = MultiSelectField(max_length=200, choices=TIPO_TERCER_MOMENTO_LIST, verbose_name='Tipo enseñanza tercer momento',max_choices=2)
    detalle_tercer_momento = models.TextField(verbose_name='Detalle enseñanza tercer momento')
    tiempo_tercer_momento = models.IntegerField(verbose_name='Tiempo tercer momento (minutos)', validators=[MinValueValidator(1)],)
    recursos_tercer_momento = models.TextField(verbose_name='Recursos didácticos tercer momento')

    # Ejes transversales
    eje_transversal = MultiSelectField(max_length=200, choices=EJE_TRANSVERSAL_LIST, max_choices=2)
    detalle_eje_transversal = models.TextField(verbose_name='Detalle eje transversal')

    # Sección 4: Evaluación dinámica (según imagen 3)
    actividad_aprendizaje = models.TextField(verbose_name='Actividad de aprendizaje')
    tecnica_evaluacion = MultiSelectField(max_length=200, choices=TECNICA_EVALUACION_LIST, verbose_name='Técnica de evaluación', max_choices=2)
    tipo_evaluacion = MultiSelectField(max_length=200, choices=TIPO_EVALUACION_LIST, verbose_name='Tipo de evaluación', max_choices=2)
    periodo_tiempo_programado = models.CharField(max_length=100, choices=PERIODO_TIEMPO_LIST, verbose_name='Periodo de tiempo programado')
    tiempo_minutos = models.IntegerField(verbose_name='Tiempo en minutos', validators=[MinValueValidator(1)])
    agente_evaluador = MultiSelectField(max_length=200, choices=AGENTE_EVALUADOR_LIST, verbose_name='Agente evaluador', max_choices=2)
    instrumento_evaluacion = models.CharField(max_length=100, choices=INSTRUMENTO_EVALUACION_LIST, verbose_name='Instrumento de evaluación')
    criterios_evaluacion = models.TextField(verbose_name='Criterios de evaluación')
    puntaje = models.IntegerField(verbose_name='Puntaje')


    guia = models.ForeignKey('Guia', on_delete=models.CASCADE, verbose_name="Guía de estudio", null=True, blank=True, related_name="silabos")
    asignacion_plan = models.ForeignKey(AsignacionPlanEstudio, on_delete=models.CASCADE, null=True, blank=True,
                                         related_name="silabo_set")


class PlanTematico(models.Model):
    UNIDADES_NOMBRES = [
        ("Primera unidad", "Primera unidad"),
        ("Segunda unidad", "Segunda unidad"),
        ("Tercera unidad", "Tercera unidad"),
        ("Cuarta unidad", "Cuarta unidad"),
        ("Quinta unidad", "Quinta unidad"),
        ("Sexta unidad", "Sexta unidad"),
    ]

    # Relación con Plan_de_estudio
    plan_estudio = models.ForeignKey("Plan_de_estudio", on_delete=models.CASCADE, related_name="plantematicos_asociados", verbose_name="Plan de Estudio Asociado", null=True, blank=True)
    # Campos de unidad 1
    unidades = models.CharField(max_length=50, choices=UNIDADES_NOMBRES, verbose_name='Unidades', null=False, blank=False)
    nombre_de_la_unidad = models.CharField(max_length=300, verbose_name='Nombre de la unidad', null=False, blank=False)
    objetivo_especificos = models.TextField(max_length=2500, verbose_name='Objetivos específicos', null=False, blank=False)
    plan_analitico = models.TextField(max_length=2500, verbose_name='Plan Analítico', null=False, blank=False)
    recomendaciones_metodologicas = models.TextField(max_length=2500, verbose_name='Recomendaciones metodológicas', null=False, blank=False)
    forma_de_evaluacion = models.TextField(max_length=2500, verbose_name='Forma de evaluación', null=False, blank=False)
    relacion_eje_contenido_launidad = models.TextField(max_length=2500, verbose_name='Relación eje contenido la unidad', null=False, blank=False)

    # Campos de unidad 2
    unidades_2 = models.CharField(max_length=50, choices=UNIDADES_NOMBRES, verbose_name='Unidades 2', null=True, blank=True)
    nombre_de_la_unidad_2 = models.CharField(max_length=300, verbose_name='Nombre de la unidad 2', null=True, blank=True)
    objetivo_especificos_2 = models.TextField(max_length=2500, verbose_name='Objetivos específicos 2', null=True, blank=True)
    plan_analitico_2 = models.TextField(max_length=2500, verbose_name='Plan Analítico 2', null=True, blank=True)
    recomendaciones_metodologicas_2 = models.TextField(max_length=2500, verbose_name='Recomendaciones metodológicas 2', null=True, blank=True)
    forma_de_evaluacion_2 = models.TextField(max_length=2500, verbose_name='Forma de evaluación 2', null=True, blank=True)
    relacion_eje_contenido_launidad_2 = models.TextField(max_length=2500, verbose_name='Relación eje contenido la unidad 2', null=True, blank=True)

    # Campos de unidad 3
    unidades_3 = models.CharField(max_length=50, choices=UNIDADES_NOMBRES, verbose_name='Unidades 3', null=True, blank=True)
    nombre_de_la_unidad_3 = models.CharField(max_length=300, verbose_name='Nombre de la unidad 3', null=True, blank=True)
    objetivo_especificos_3 = models.TextField(max_length=2500, verbose_name='Objetivos específicos 3', null=True, blank=True)
    plan_analitico_3 = models.TextField(max_length=2500, verbose_name='Plan Analítico 3', null=True, blank=True)
    recomendaciones_metodologicas_3 = models.TextField(max_length=2500, verbose_name='Recomendaciones metodológicas 3', null=True, blank=True)
    forma_de_evaluacion_3 = models.TextField(max_length=2500, verbose_name='Forma de evaluación 3', null=True, blank=True)
    relacion_eje_contenido_launidad_3 = models.TextField(max_length=2500, verbose_name='Relación eje contenido la unidad 3', null=True, blank=True)

    # Campos de unidad 4
    unidades_4 = models.CharField(max_length=50, choices=UNIDADES_NOMBRES, verbose_name='Unidades 4', null=True, blank=True)
    nombre_de_la_unidad_4 = models.CharField(max_length=300, verbose_name='Nombre de la unidad 4', null=True, blank=True)
    objetivo_especificos_4 = models.TextField(max_length=2500, verbose_name='Objetivos específicos 4', null=True, blank=True)
    plan_analitico_4 = models.TextField(max_length=2500, verbose_name='Plan Analítico 4', null=True, blank=True)
    recomendaciones_metodologicas_4 = models.TextField(max_length=2500, verbose_name='Recomendaciones metodológicas 4', null=True, blank=True)
    forma_de_evaluacion_4 = models.TextField(max_length=2500, verbose_name='Forma de evaluación 4', null=True, blank=True)
    relacion_eje_contenido_launidad_4 = models.TextField(max_length=2500, verbose_name='Relación eje contenido la unidad 4', null=True, blank=True)

    # Campos de unidad 5
    unidades_5 = models.CharField(max_length=50, choices=UNIDADES_NOMBRES, verbose_name='Unidades 5', null=True, blank=True)
    nombre_de_la_unidad_5 = models.CharField(max_length=300, verbose_name='Nombre de la unidad 5', null=True, blank=True)
    objetivo_especificos_5 = models.TextField(max_length=2500, verbose_name='Objetivos específicos 5', null=True, blank=True)
    plan_analitico_5 = models.TextField(max_length=2500, verbose_name='Plan Analítico 5', null=True, blank=True)
    recomendaciones_metodologicas_5 = models.TextField(max_length=2500, verbose_name='Recomendaciones metodológicas 5', null=True, blank=True)
    forma_de_evaluacion_5 = models.TextField(max_length=2500, verbose_name='Forma de evaluación 5', null=True, blank=True)
    relacion_eje_contenido_launidad_5 = models.TextField(max_length=2500, verbose_name='Relación eje contenido la unidad 5', null=True, blank=True)

    # Campos de unidad 6
    unidades_6 = models.CharField(max_length=50, choices=UNIDADES_NOMBRES, verbose_name='Unidades 6', null=True, blank=True)
    nombre_de_la_unidad_6 = models.CharField(max_length=300, verbose_name='Nombre de la unidad 6', null=True, blank=True)
    objetivo_especificos_6 = models.TextField(max_length=2500, verbose_name='Objetivos específicos 6', null=True, blank=True)
    plan_analitico_6 = models.TextField(max_length=2500, verbose_name='Plan Analítico 6', null=True, blank=True)
    recomendaciones_metodologicas_6 = models.TextField(max_length=2500, verbose_name='Recomendaciones metodológicas 6', null=True, blank=True)
    forma_de_evaluacion_6 = models.TextField(max_length=2500, verbose_name='Forma de evaluación 6', null=True, blank=True)
    relacion_eje_contenido_launidad_6 = models.TextField(max_length=2500, verbose_name='Relación eje contenido la unidad 6', null=True, blank=True)

    class Meta:
        verbose_name = "Programa de asignatura 2015-2025"
        verbose_name_plural = "Programas de asignatura 2015-2025"

    def __str__(self):
        return f'{self.unidades} - {self.nombre_de_la_unidad}'

    def get_numero_unidades_completadas(self):
        count = 0
        # Check if the main unit name field is filled
        if self.nombre_de_la_unidad and self.nombre_de_la_unidad.strip():
            count += 1
        # Check optional unit name fields
        if self.nombre_de_la_unidad_2 and self.nombre_de_la_unidad_2.strip():
            count += 1
        if self.nombre_de_la_unidad_3 and self.nombre_de_la_unidad_3.strip():
            count += 1
        if self.nombre_de_la_unidad_4 and self.nombre_de_la_unidad_4.strip():
            count += 1
        if self.nombre_de_la_unidad_5 and self.nombre_de_la_unidad_5.strip():
            count += 1
        if self.nombre_de_la_unidad_6 and self.nombre_de_la_unidad_6.strip():
            count += 1
        return count

    def clean(self):
        pass


class ProgramaAsignatura2026(models.Model):
    # Fundamentación y Descripción
    fundamentacion = models.TextField(verbose_name="Fundamentación")
    relacion_unidades = models.TextField(verbose_name="Relación entre las unidades temáticas")
    aportes_perfil = models.TextField(verbose_name="Aportes al perfil profesional")
    valores = models.TextField(verbose_name="Valores que se desarrollan")
    ejes_transversales = models.TextField(verbose_name="Ejes Transversales")

    # Objetivos Generales
    objetivo_conceptual = models.TextField(verbose_name="Objetivo General - Conceptual")
    objetivo_procedimental = models.TextField(verbose_name="Objetivo General - Procedimental")
    objetivo_actitudinal = models.TextField(verbose_name="Objetivo General - Actitudinal")
    
    plan_estudio = models.ForeignKey("Plan_de_estudio", on_delete=models.CASCADE, related_name="programas_2026_asociados", verbose_name="Plan de Estudio Asociado", null=True, blank=True)

    # UNIDADES (Repetimos estructura de I a VI como en el modelo anterior para consistencia en Admin)
    # UNIDAD I
    unidad_1_nombre = models.CharField(max_length=255, verbose_name="Nombre Unidad I", blank=True, default="")
    unidad_1_horas_teoricas = models.IntegerField(verbose_name="Horas Teóricas I", default=0)
    unidad_1_horas_practicas = models.IntegerField(verbose_name="Horas Prácticas I", default=0)
    unidad_1_horas_independientes = models.IntegerField(verbose_name="Horas Estudio Indep. I", default=0)
    unidad_1_objetivos_especificos = models.TextField(verbose_name="Objetivos Específicos I", blank=True, default="")
    unidad_1_contenido = models.TextField(verbose_name="Contenido Temático I", blank=True, default="")
    unidad_1_mediacion = models.TextField(verbose_name="Mediación Pedagógica I", blank=True, default="")
    unidad_1_evaluacion = models.TextField(verbose_name="Evaluación I", blank=True, default="")

    # UNIDAD II
    unidad_2_nombre = models.CharField(max_length=255, verbose_name="Nombre Unidad II", blank=True, default="")
    unidad_2_horas_teoricas = models.IntegerField(verbose_name="Horas Teóricas II", default=0)
    unidad_2_horas_practicas = models.IntegerField(verbose_name="Horas Prácticas II", default=0)
    unidad_2_horas_independientes = models.IntegerField(verbose_name="Horas Estudio Indep. II", default=0)
    unidad_2_objetivos_especificos = models.TextField(verbose_name="Objetivos Específicos II", blank=True, default="")
    unidad_2_contenido = models.TextField(verbose_name="Contenido Temático II", blank=True, default="")
    unidad_2_mediacion = models.TextField(verbose_name="Mediación Pedagógica II", blank=True, default="")
    unidad_2_evaluacion = models.TextField(verbose_name="Evaluación II", blank=True, default="")

    # UNIDAD III
    unidad_3_nombre = models.CharField(max_length=255, verbose_name="Nombre Unidad III", blank=True, default="")
    unidad_3_horas_teoricas = models.IntegerField(verbose_name="Horas Teóricas III", default=0)
    unidad_3_horas_practicas = models.IntegerField(verbose_name="Horas Prácticas III", default=0)
    unidad_3_horas_independientes = models.IntegerField(verbose_name="Horas Estudio Indep. III", default=0)
    unidad_3_objetivos_especificos = models.TextField(verbose_name="Objetivos Específicos III", blank=True, default="")
    unidad_3_contenido = models.TextField(verbose_name="Contenido Temático III", blank=True, default="")
    unidad_3_mediacion = models.TextField(verbose_name="Mediación Pedagógica III", blank=True, default="")
    unidad_3_evaluacion = models.TextField(verbose_name="Evaluación III", blank=True, default="")

    # UNIDAD IV
    unidad_4_nombre = models.CharField(max_length=255, verbose_name="Nombre Unidad IV", blank=True, default="")
    unidad_4_horas_teoricas = models.IntegerField(verbose_name="Horas Teóricas IV", default=0)
    unidad_4_horas_practicas = models.IntegerField(verbose_name="Horas Prácticas IV", default=0)
    unidad_4_horas_independientes = models.IntegerField(verbose_name="Horas Estudio Indep. IV", default=0)
    unidad_4_objetivos_especificos = models.TextField(verbose_name="Objetivos Específicos IV", blank=True, default="")
    unidad_4_contenido = models.TextField(verbose_name="Contenido Temático IV", blank=True, default="")
    unidad_4_mediacion = models.TextField(verbose_name="Mediación Pedagógica IV", blank=True, default="")
    unidad_4_evaluacion = models.TextField(verbose_name="Evaluación IV", blank=True, default="")

    # UNIDAD V
    unidad_5_nombre = models.CharField(max_length=255, verbose_name="Nombre Unidad V", blank=True, default="")
    unidad_5_horas_teoricas = models.IntegerField(verbose_name="Horas Teóricas V", default=0)
    unidad_5_horas_practicas = models.IntegerField(verbose_name="Horas Prácticas V", default=0)
    unidad_5_horas_independientes = models.IntegerField(verbose_name="Horas Estudio Indep. V", default=0)
    unidad_5_objetivos_especificos = models.TextField(verbose_name="Objetivos Específicos V", blank=True, default="")
    unidad_5_contenido = models.TextField(verbose_name="Contenido Temático V", blank=True, default="")
    unidad_5_mediacion = models.TextField(verbose_name="Mediación Pedagógica V", blank=True, default="")
    unidad_5_evaluacion = models.TextField(verbose_name="Evaluación V", blank=True, default="")

    # UNIDAD VI (Extra just in case, or to match 6 units in old model)
    unidad_6_nombre = models.CharField(max_length=255, verbose_name="Nombre Unidad VI", blank=True, default="")
    unidad_6_horas_teoricas = models.IntegerField(verbose_name="Horas Teóricas VI", default=0)
    unidad_6_horas_practicas = models.IntegerField(verbose_name="Horas Prácticas VI", default=0)
    unidad_6_horas_independientes = models.IntegerField(verbose_name="Horas Estudio Indep. VI", default=0)
    unidad_6_objetivos_especificos = models.TextField(verbose_name="Objetivos Específicos VI", blank=True, default="")
    unidad_6_contenido = models.TextField(verbose_name="Contenido Temático VI", blank=True, default="")
    unidad_6_mediacion = models.TextField(verbose_name="Mediación Pedagógica VI", blank=True, default="")
    unidad_6_evaluacion = models.TextField(verbose_name="Evaluación VI", blank=True, default="")

    # Bibliografía
    bibliografia_basica = models.TextField(verbose_name="Bibliografía Básica", blank=True, null=True)
    bibliografia_complementaria = models.TextField(verbose_name="Bibliografía Complementaria", blank=True, null=True)
    webgrafia = models.TextField(verbose_name="Web-grafía", blank=True, null=True)
    
    class Meta:
        verbose_name = "Programa de asignatura 2026"
        verbose_name_plural = "Programas de asignatura 2026"

    def __str__(self):
        return f"{self.plan_estudio} - Programa 2026"


class Guia(models.Model):
    """
    Representa una guía de estudio dentro del sílabo.
    """

    TIPO_OBJETIVO_LIST = (
        ('Conceptual', 'Conceptual'),
        ('Procedimental', 'Procedimental'),
        ('Actitudinal', 'Actitudinal'),
    )

    silabo = models.ForeignKey(Silabo, on_delete=models.CASCADE, related_name="guias")
    # Sección 1: Información General
    numero_encuentro = models.IntegerField(verbose_name="N° Encuentro")
    fecha = models.DateField(verbose_name="Fecha")
    unidad = models.CharField(max_length=255, choices=Silabo.UNIDAD_LIST, verbose_name="N° Unidad")
    nombre_de_la_unidad = models.CharField(max_length=255, verbose_name="Nombre de la unidad")

    # tarea 1
    tipo_objetivo_1 = models.CharField(max_length=100, choices=TIPO_OBJETIVO_LIST, verbose_name="Tipo 1")
    objetivo_aprendizaje_1 = models.TextField(verbose_name="Objetivo aprendizaje 1")
    contenido_tematico_1 = models.TextField(verbose_name="Contenido temático 1")
    actividad_aprendizaje_1 = models.TextField(verbose_name="Actividad aprendizaje 1")
    tecnica_evaluacion_1 = models.CharField(max_length=100, choices=Silabo.TECNICA_EVALUACION_LIST, verbose_name="Técnica evaluación 1")
    tipo_evaluacion_1 = models.CharField(max_length=100, choices=Silabo.TIPO_EVALUACION_LIST, verbose_name="Tipo evaluación 1")
    instrumento_evaluacion_1 = models.CharField(max_length=100, choices=Silabo.INSTRUMENTO_EVALUACION_LIST, verbose_name="Instrumento evaluación 1")
    criterios_evaluacion_1 = models.TextField(verbose_name="Criterios evaluación 1")
    agente_evaluador_1 = MultiSelectField(max_length=200, choices=Silabo.AGENTE_EVALUADOR_LIST, verbose_name="Agente evaluador 1",  max_choices=2)
    tiempo_minutos_1 = models.IntegerField(verbose_name="Tiempo minutos 1", validators=[MinValueValidator(1)])
    recursos_didacticos_1 = models.TextField(verbose_name="Recursos didácticos 1")
    periodo_tiempo_programado_1 = models.CharField(max_length=100, choices=Silabo.PERIODO_TIEMPO_LIST, verbose_name="Periodo tiempo programado 1")
    puntaje_1 = models.IntegerField(verbose_name="Puntaje 1")
    fecha_entrega_1 = models.DateField(verbose_name="Fecha entrega 1")

    # tarea 2
    tipo_objetivo_2 = models.CharField(max_length=100, choices=TIPO_OBJETIVO_LIST, verbose_name="Tipo 2", null=True, blank=True)
    objetivo_aprendizaje_2 = models.TextField(verbose_name="Objetivo aprendizaje 2", null=True, blank=True)
    contenido_tematico_2 = models.TextField(verbose_name="Contenido temático 2", null=True, blank=True)
    actividad_aprendizaje_2 = models.TextField(verbose_name="Actividad aprendizaje 2", null=True, blank=True)
    tecnica_evaluacion_2 = models.CharField(max_length=100, choices=Silabo.TECNICA_EVALUACION_LIST, verbose_name="Técnica evaluación 2", null=True, blank=True)
    tipo_evaluacion_2 = models.CharField(max_length=100, choices=Silabo.TIPO_EVALUACION_LIST, verbose_name="Tipo evaluación 2", null=True, blank=True)
    instrumento_evaluacion_2 = models.CharField(max_length=100, choices=Silabo.INSTRUMENTO_EVALUACION_LIST, verbose_name="Instrumento evaluación 2", null=True, blank=True)
    criterios_evaluacion_2 = models.TextField(verbose_name="Criterios evaluación 2", null=True, blank=True)
    agente_evaluador_2 = MultiSelectField(max_length=100, choices=Silabo.AGENTE_EVALUADOR_LIST, verbose_name="Agente evaluador 2", max_choices=2, null=True, blank=True)
    tiempo_minutos_2 = models.IntegerField(verbose_name="Tiempo minutos 2", validators=[MinValueValidator(1)], null=True, blank=True)
    recursos_didacticos_2 = models.TextField(verbose_name="Recursos didácticos 2", null=True, blank=True)
    periodo_tiempo_programado_2 = models.CharField(max_length=100, choices=Silabo.PERIODO_TIEMPO_LIST, verbose_name="Periodo tiempo programado 2", null=True, blank=True)
    puntaje_2 = models.IntegerField(verbose_name="Puntaje 2", null=True, blank=True)
    fecha_entrega_2 = models.DateField(verbose_name="Fecha entrega 2", null=True, blank=True)

    # tarea 3
    tipo_objetivo_3 = models.CharField(max_length=100, choices=TIPO_OBJETIVO_LIST, verbose_name="Tipo 3", null=True, blank=True)
    objetivo_aprendizaje_3 = models.TextField(verbose_name="Objetivo aprendizaje 3", null=True, blank=True)
    contenido_tematico_3 = models.TextField(verbose_name="Contenido temático 3", null=True, blank=True)
    actividad_aprendizaje_3 = models.TextField(verbose_name="Actividad aprendizaje 3", null=True, blank=True)
    tecnica_evaluacion_3 = models.CharField(max_length=100, choices=Silabo.TECNICA_EVALUACION_LIST, verbose_name="Técnica evaluación 3", null=True, blank=True)
    tipo_evaluacion_3 = models.CharField(max_length=100, choices=Silabo.TIPO_EVALUACION_LIST, verbose_name="Tipo evaluación 3", null=True, blank=True)
    instrumento_evaluacion_3 = models.CharField(max_length=100, choices=Silabo.INSTRUMENTO_EVALUACION_LIST, verbose_name="Instrumento evaluación 3", null=True, blank=True)
    criterios_evaluacion_3 = models.TextField(verbose_name="Criterios evaluación 3", null=True, blank=True)
    agente_evaluador_3 = MultiSelectField(max_length=200, choices=Silabo.AGENTE_EVALUADOR_LIST, verbose_name="Agente evaluador 3", max_choices=2, null=True, blank=True)
    tiempo_minutos_3 = models.IntegerField(verbose_name="Tiempo minutos 3", validators=[MinValueValidator(1)], null=True, blank=True)
    recursos_didacticos_3 = models.TextField(verbose_name="Recursos didácticos 3", null=True, blank=True)
    periodo_tiempo_programado_3 = models.CharField(max_length=100, choices=Silabo.PERIODO_TIEMPO_LIST, verbose_name="Periodo tiempo programado 3", null=True, blank=True)
    puntaje_3 = models.IntegerField(verbose_name="Puntaje 3", null=True, blank=True)
    fecha_entrega_3 = models.DateField(verbose_name="Fecha entrega 3", null=True, blank=True)

    # tarea 4
    tipo_objetivo_4 = models.CharField(max_length=100, choices=TIPO_OBJETIVO_LIST, verbose_name="Tipo 4", null=True, blank=True)
    objetivo_aprendizaje_4 = models.TextField(verbose_name="Objetivo aprendizaje 4", null=True, blank=True)
    contenido_tematico_4 = models.TextField(verbose_name="Contenido temático 4", null=True, blank=True)
    actividad_aprendizaje_4 = models.TextField(verbose_name="Actividad aprendizaje 4", null=True, blank=True)
    tecnica_evaluacion_4 = models.CharField(max_length=100, choices=Silabo.TECNICA_EVALUACION_LIST, verbose_name="Técnica evaluación 4", null=True, blank=True)
    tipo_evaluacion_4 = models.CharField(max_length=200, choices=Silabo.TIPO_EVALUACION_LIST, verbose_name="Tipo evaluación 4", null=True, blank=True)
    instrumento_evaluacion_4 = models.CharField(max_length=100, choices=Silabo.INSTRUMENTO_EVALUACION_LIST, verbose_name="Instrumento evaluación 4", null=True, blank=True)
    criterios_evaluacion_4 = models.TextField(verbose_name="Criterios evaluación 4", null=True, blank=True)
    agente_evaluador_4 = MultiSelectField(max_length=200, choices=Silabo.AGENTE_EVALUADOR_LIST, verbose_name="Agente evaluador 4", max_choices=2, null=True, blank=True)
    tiempo_minutos_4 = models.IntegerField(verbose_name="Tiempo minutos 4", validators=[MinValueValidator(1)], null=True, blank=True)
    recursos_didacticos_4 = models.TextField(verbose_name="Recursos didácticos 4", null=True, blank=True)
    periodo_tiempo_programado_4 = models.CharField(max_length=100, choices=Silabo.PERIODO_TIEMPO_LIST, verbose_name="Periodo tiempo programado 4", null=True, blank=True)
    puntaje_4 = models.IntegerField(verbose_name="Puntaje 4", null=True, blank=True)
    fecha_entrega_4 = models.DateField(verbose_name="Fecha entrega 4", null=True, blank=True)

    def __str__(self):
        return f"Guía {self.numero_encuentro} - {self.unidad} - {self.fecha}"
