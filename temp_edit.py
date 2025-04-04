class PlanTematico(models.Model):
    UNIDADES_NOMBRES = [
        ('Primera unidad', 'Primera unidad'),
        ('Segunda unidad', 'Segunda unidad'),
        ('Tercera unidad', 'Tercera unidad'),
        ('Cuarta unidad', 'Cuarta unidad'),
    ]
    
    # Relación con Plan_de_estudio
    plan_estudio = models.ForeignKey('Plan_de_estudio', on_delete=models.CASCADE, 
                                 related_name='plantematicos_asociados', 
                                 verbose_name='Plan de Estudio Asociado',
                                 null=True, blank=True)
    
    # Campos de unidad 1
