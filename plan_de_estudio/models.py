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
    plan_tematico = models.FileField(upload_to='planes_tematicos/', null=True, blank=True)
    plan_tematico_ref = models.ForeignKey('PlanTematico', on_delete=models.CASCADE, verbose_name='Plan temático relacionado', related_name='planes_de_estudio', null=True, blank=True)
    documento_adjunto = models.FileField(upload_to='documentos_plan_estudio/', null=True, blank=True, verbose_name='Documento adjunto')
    

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
            
        # Validación para plan_tematico_ref
        if self.plan_tematico_ref:
            # Verificar si este plan temático ya está asignado a otro plan de estudio
            existing_assignment = Plan_de_estudio.objects.filter(
                plan_tematico_ref=self.plan_tematico_ref
            ).exclude(pk=self.pk).exists()
            
            if existing_assignment:
                raise ValidationError("Este plan temático ya está asignado a otro plan de estudio.")


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
    codigo = models.CharField(max_length=10)
    
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
    tiempo_primer_momento = models.IntegerField(verbose_name='Tiempo primer momento (minutos)')
    recursos_primer_momento = models.TextField(verbose_name='Recursos didácticos primer momento')
    
    # Segundo momento didáctico (fase elaboración)
    tipo_segundo_momento_claseteoria = models.CharField(max_length=100, choices=TIPO_SEGUNDO_MOMENTO_TEORIA_LIST, verbose_name='Tipo enseñanza clase teórica')
    clase_teorica = models.TextField(verbose_name='Clase teórica')
    tipo_segundo_momento_practica = models.CharField(max_length=100, choices=TIPO_SEGUNDO_MOMENTO_PRACTICA_LIST, verbose_name='Tipo enseñanza clase práctica')
    clase_practica = models.TextField(verbose_name='Clase práctica')
    tiempo_segundo_momento = models.IntegerField(verbose_name='Tiempo segundo momento (minutos)')
    recursos_segundo_momento = models.TextField(verbose_name='Recursos didácticos segundo momento')
    
    # Tercer momento didáctico (fase salida)
    tipo_tercer_momento = models.CharField(max_length=100, choices=TIPO_TERCER_MOMENTO_LIST, verbose_name='Tipo enseñanza tercer momento')
    detalle_tercer_momento = models.TextField(verbose_name='Detalle enseñanza tercer momento')
    tiempo_tercer_momento = models.IntegerField(verbose_name='Tiempo tercer momento (minutos)')
    recursos_tercer_momento = models.TextField(verbose_name='Recursos didácticos tercer momento')
    
    # Ejes transversales
    eje_transversal = models.CharField(max_length=255, choices=EJE_TRANSVERSAL_LIST)
    detalle_eje_transversal = models.TextField(verbose_name='Detalle eje transversal')
    
    # Sección 4: Evaluación dinámica (según imagen 3)
    actividad_aprendizaje = models.TextField(verbose_name='Actividad de aprendizaje')
    tecnica_evaluacion = models.CharField(max_length=100, choices=TECNICA_EVALUACION_LIST, verbose_name='Técnica de evaluación')
    tipo_evaluacion = models.CharField(max_length=100, choices=TIPO_EVALUACION_LIST, verbose_name='Tipo de evaluación')
    periodo_tiempo_programado = models.CharField(max_length=100, choices=PERIODO_TIEMPO_LIST, verbose_name='Periodo de tiempo programado')
    tiempo_minutos = models.IntegerField(verbose_name='Tiempo en minutos')
    agente_evaluador = models.CharField(max_length=100, choices=AGENTE_EVALUADOR_LIST, verbose_name='Agente evaluador')
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
    objetivo_especificos = models.TextField(max_length=1500, verbose_name='Objetivos específicos', null=False, blank=False)
    plan_analitico = models.TextField(max_length=1500, verbose_name='Plan Analítico', null=False, blank=False)
    recomendaciones_metodologicas = models.TextField(max_length=1500, verbose_name='Recomendaciones metodológicas', null=False, blank=False)
    forma_de_evaluacion = models.TextField(max_length=1000, verbose_name='Forma de evaluación', null=False, blank=False) 
    relacion_eje_contenido_launidad = models.TextField(max_length=1000, verbose_name='Relación eje contenido la unidad', null=False, blank=False)
    
    # Campos de unidad 2
    unidades_2 = models.CharField(max_length=50, choices=UNIDADES_NOMBRES, verbose_name='Unidades 2', null=True, blank=True)
    nombre_de_la_unidad_2 = models.CharField(max_length=300, verbose_name='Nombre de la unidad 2', null=True, blank=True)
    objetivo_especificos_2 = models.TextField(max_length=1500, verbose_name='Objetivos específicos 2', null=True, blank=True)
    plan_analitico_2 = models.TextField(max_length=1500, verbose_name='Plan Analítico 2', null=True, blank=True)
    recomendaciones_metodologicas_2 = models.TextField(max_length=1500, verbose_name='Recomendaciones metodológicas 2', null=True, blank=True)
    forma_de_evaluacion_2 = models.TextField(max_length=1000, verbose_name='Forma de evaluación 2', null=True, blank=True) 
    relacion_eje_contenido_launidad_2 = models.TextField(max_length=1000, verbose_name='Relación eje contenido la unidad 2', null=True, blank=True)
    
    # Campos de unidad 3
    unidades_3 = models.CharField(max_length=50, choices=UNIDADES_NOMBRES, verbose_name='Unidades 3', null=True, blank=True)
    nombre_de_la_unidad_3 = models.CharField(max_length=300, verbose_name='Nombre de la unidad 3', null=True, blank=True)
    objetivo_especificos_3 = models.TextField(max_length=1500, verbose_name='Objetivos específicos 3', null=True, blank=True)
    plan_analitico_3 = models.TextField(max_length=1500, verbose_name='Plan Analítico 3', null=True, blank=True)
    recomendaciones_metodologicas_3 = models.TextField(max_length=1500, verbose_name='Recomendaciones metodológicas 3', null=True, blank=True)
    forma_de_evaluacion_3 = models.TextField(max_length=1000, verbose_name='Forma de evaluación 3', null=True, blank=True) 
    relacion_eje_contenido_launidad_3 = models.TextField(max_length=1000, verbose_name='Relación eje contenido la unidad 3', null=True, blank=True)
    
    # Campos de unidad 4
    unidades_4 = models.CharField(max_length=50, choices=UNIDADES_NOMBRES, verbose_name='Unidades 4', null=True, blank=True)
    nombre_de_la_unidad_4 = models.CharField(max_length=300, verbose_name='Nombre de la unidad 4', null=True, blank=True)
    objetivo_especificos_4 = models.TextField(max_length=1500, verbose_name='Objetivos específicos 4', null=True, blank=True)
    plan_analitico_4 = models.TextField(max_length=1500, verbose_name='Plan Analítico 4', null=True, blank=True)
    recomendaciones_metodologicas_4 = models.TextField(max_length=1500, verbose_name='Recomendaciones metodológicas 4', null=True, blank=True)
    forma_de_evaluacion_4 = models.TextField(max_length=1000, verbose_name='Forma de evaluación 4', null=True, blank=True) 
    relacion_eje_contenido_launidad_4 = models.TextField(max_length=1000, verbose_name='Relación eje contenido la unidad 4', null=True, blank=True)
    
    # Campos de unidad 5
    unidades_5 = models.CharField(max_length=50, choices=UNIDADES_NOMBRES, verbose_name='Unidades 5', null=True, blank=True)
    nombre_de_la_unidad_5 = models.CharField(max_length=300, verbose_name='Nombre de la unidad 5', null=True, blank=True)
    objetivo_especificos_5 = models.TextField(max_length=1500, verbose_name='Objetivos específicos 5', null=True, blank=True)
    plan_analitico_5 = models.TextField(max_length=1500, verbose_name='Plan Analítico 5', null=True, blank=True)
    recomendaciones_metodologicas_5 = models.TextField(max_length=1500, verbose_name='Recomendaciones metodológicas 5', null=True, blank=True)
    forma_de_evaluacion_5 = models.TextField(max_length=1000, verbose_name='Forma de evaluación 5', null=True, blank=True) 
    relacion_eje_contenido_launidad_5 = models.TextField(max_length=1000, verbose_name='Relación eje contenido la unidad 5', null=True, blank=True)
    
    # Campos de unidad 6
    unidades_6 = models.CharField(max_length=50, choices=UNIDADES_NOMBRES, verbose_name='Unidades 6', null=True, blank=True)
    nombre_de_la_unidad_6 = models.CharField(max_length=300, verbose_name='Nombre de la unidad 6', null=True, blank=True)
    objetivo_especificos_6 = models.TextField(max_length=1500, verbose_name='Objetivos específicos 6', null=True, blank=True)
    plan_analitico_6 = models.TextField(max_length=1500, verbose_name='Plan Analítico 6', null=True, blank=True)
    recomendaciones_metodologicas_6 = models.TextField(max_length=1500, verbose_name='Recomendaciones metodológicas 6', null=True, blank=True)
    forma_de_evaluacion_6 = models.TextField(max_length=1000, verbose_name='Forma de evaluación 6', null=True, blank=True) 
    relacion_eje_contenido_launidad_6 = models.TextField(max_length=1000, verbose_name='Relación eje contenido la unidad 6', null=True, blank=True)
    
    class Meta:
        pass

    def __str__(self):
        return f'{self.unidades} - {self.nombre_de_la_unidad}'
        
    def clean(self):
        pass
        

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
    agente_evaluador_1 = models.CharField(max_length=100, choices=Silabo.AGENTE_EVALUADOR_LIST, verbose_name="Agente evaluador 1")
    tiempo_minutos_1 = models.IntegerField(verbose_name="Tiempo minutos 1")
    recursos_didacticos_1 = models.TextField(verbose_name="Recursos didácticos 1")
    periodo_tiempo_programado_1 = models.CharField(max_length=100, choices=Silabo.PERIODO_TIEMPO_LIST, verbose_name="Periodo tiempo programado 1")
    puntaje_1 = models.IntegerField(verbose_name="Puntaje 1")
    fecha_entrega_1 = models.DateField(verbose_name="Fecha entrega 1")
    
    # tarea 2
    tipo_objetivo_2 = models.CharField(max_length=100, choices=TIPO_OBJETIVO_LIST, verbose_name="Tipo 2")
    objetivo_aprendizaje_2 = models.TextField(verbose_name="Objetivo aprendizaje 2")
    contenido_tematico_2 = models.TextField(verbose_name="Contenido temático 2")
    actividad_aprendizaje_2 = models.TextField(verbose_name="Actividad aprendizaje 2")
    tecnica_evaluacion_2 = models.CharField(max_length=100, choices=Silabo.TECNICA_EVALUACION_LIST, verbose_name="Técnica evaluación 2")
    tipo_evaluacion_2 = models.CharField(max_length=100, choices=Silabo.TIPO_EVALUACION_LIST, verbose_name="Tipo evaluación 2")
    instrumento_evaluacion_2 = models.CharField(max_length=100, choices=Silabo.INSTRUMENTO_EVALUACION_LIST, verbose_name="Instrumento evaluación 2")
    criterios_evaluacion_2 = models.TextField(verbose_name="Criterios evaluación 2")
    agente_evaluador_2 = models.CharField(max_length=100, choices=Silabo.AGENTE_EVALUADOR_LIST, verbose_name="Agente evaluador 2")
    tiempo_minutos_2 = models.IntegerField(verbose_name="Tiempo minutos 2")
    recursos_didacticos_2 = models.TextField(verbose_name="Recursos didácticos 2")
    periodo_tiempo_programado_2 = models.CharField(max_length=100, choices=Silabo.PERIODO_TIEMPO_LIST, verbose_name="Periodo tiempo programado 2")
    puntaje_2 = models.IntegerField(verbose_name="Puntaje 2")
    fecha_entrega_2 = models.DateField(verbose_name="Fecha entrega 2")
    
    # tarea 3
    tipo_objetivo_3 = models.CharField(max_length=100, choices=TIPO_OBJETIVO_LIST, verbose_name="Tipo 3")
    objetivo_aprendizaje_3 = models.TextField(verbose_name="Objetivo aprendizaje 3")
    contenido_tematico_3 = models.TextField(verbose_name="Contenido temático 3")
    actividad_aprendizaje_3 = models.TextField(verbose_name="Actividad aprendizaje 3")
    tecnica_evaluacion_3 = models.CharField(max_length=100, choices=Silabo.TECNICA_EVALUACION_LIST, verbose_name="Técnica evaluación 3")
    tipo_evaluacion_3 = models.CharField(max_length=100, choices=Silabo.TIPO_EVALUACION_LIST, verbose_name="Tipo evaluación 3")
    instrumento_evaluacion_3 = models.CharField(max_length=100, choices=Silabo.INSTRUMENTO_EVALUACION_LIST, verbose_name="Instrumento evaluación 3")
    criterios_evaluacion_3 = models.TextField(verbose_name="Criterios evaluación 3")
    agente_evaluador_3 = models.CharField(max_length=100, choices=Silabo.AGENTE_EVALUADOR_LIST, verbose_name="Agente evaluador 3")
    tiempo_minutos_3 = models.IntegerField(verbose_name="Tiempo minutos 3")
    recursos_didacticos_3 = models.TextField(verbose_name="Recursos didácticos 3")
    periodo_tiempo_programado_3 = models.CharField(max_length=100, choices=Silabo.PERIODO_TIEMPO_LIST, verbose_name="Periodo tiempo programado 3")
    puntaje_3 = models.IntegerField(verbose_name="Puntaje 3")
    fecha_entrega_3 = models.DateField(verbose_name="Fecha entrega 3")
    
    # tarea 4
    tipo_objetivo_4 = models.CharField(max_length=100, choices=TIPO_OBJETIVO_LIST, verbose_name="Tipo 4")
    objetivo_aprendizaje_4 = models.TextField(verbose_name="Objetivo aprendizaje 4")
    contenido_tematico_4 = models.TextField(verbose_name="Contenido temático 4")
    actividad_aprendizaje_4 = models.TextField(verbose_name="Actividad aprendizaje 4")
    tecnica_evaluacion_4 = models.CharField(max_length=100, choices=Silabo.TECNICA_EVALUACION_LIST, verbose_name="Técnica evaluación 4")
    tipo_evaluacion_4 = models.CharField(max_length=100, choices=Silabo.TIPO_EVALUACION_LIST, verbose_name="Tipo evaluación 4")
    instrumento_evaluacion_4 = models.CharField(max_length=100, choices=Silabo.INSTRUMENTO_EVALUACION_LIST, verbose_name="Instrumento evaluación 4")
    criterios_evaluacion_4 = models.TextField(verbose_name="Criterios evaluación 4")
    agente_evaluador_4 = models.CharField(max_length=100, choices=Silabo.AGENTE_EVALUADOR_LIST, verbose_name="Agente evaluador 4")
    tiempo_minutos_4 = models.IntegerField(verbose_name="Tiempo minutos 4")
    recursos_didacticos_4 = models.TextField(verbose_name="Recursos didácticos 4")
    periodo_tiempo_programado_4 = models.CharField(max_length=100, choices=Silabo.PERIODO_TIEMPO_LIST, verbose_name="Periodo tiempo programado 4")
    puntaje_4 = models.IntegerField(verbose_name="Puntaje 4")
    fecha_entrega_4 = models.DateField(verbose_name="Fecha entrega 4")
    
    def __str__(self):
        return f"Guía {self.numero_encuentro} - {self.unidad} - {self.fecha}"
