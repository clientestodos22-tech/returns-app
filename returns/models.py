from django.db import models
from django.contrib.auth.models import User


class ReturnRequest(models.Model):
    ESTADO_CHOICES = [
        ('RECIBIDO', 'Recibido'),
        ('EN_REVISION', 'En revisión'),
        ('OBSERVADO', 'Pendiente corrección'),
        ('APROBADO', 'Aprobado'),
        ('RECHAZADO', 'Rechazado'),
        ('CERRADO', 'Cerrado'),
    ]

    fecha_recepcion = models.DateField(
        verbose_name='Fecha Recepción'
    )

    numero_documento = models.CharField(
        max_length=100,
        verbose_name='N° Documento'
    )

    documento_ingreso = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        verbose_name='Documento de ingreso / NC cliente'
    )

    cliente = models.CharField(
        max_length=150,
        verbose_name='Cliente'
    )

    sku = models.CharField(
        max_length=100,
        verbose_name='SKU'
    )

    cantidad = models.PositiveIntegerField(
        verbose_name='Cantidad'
    )

    codigo_numerico = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='Código Numérico'
    )

    serie = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='Serie'
    )

    ubicacion = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        verbose_name='Ubicación'
    )

    numero_dcto_estado = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        verbose_name='N° Dcto/Estado'
    )

    responsable = models.CharField(
        max_length=150,
        blank=True,
        verbose_name='Responsable'
    )

    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='RECIBIDO',
        verbose_name='Estado'
    )

    documento_adjunto = models.FileField(
        upload_to='returns/documentos/',
        blank=True,
        null=True,
        verbose_name='Documento adjunto'
    )

    foto_evidencia = models.ImageField(
        upload_to='returns/fotos/',
        blank=True,
        null=True,
        verbose_name='Foto evidencia'
    )

    observaciones = models.TextField(
        blank=True,
        null=True,
        verbose_name='Observaciones'
    )

    # Respuesta / gestión del cliente
    respuesta_cliente = models.TextField(
        blank=True,
        null=True,
        verbose_name='Observaciones del cliente'
    )

    documento_respuesta_cliente = models.FileField(
        upload_to='returns/respuestas/documentos/',
        blank=True,
        null=True,
        verbose_name='Documento adjunto cliente'
    )

    foto_respuesta_cliente = models.ImageField(
        upload_to='returns/respuestas/fotos/',
        blank=True,
        null=True,
        verbose_name='Foto evidencia cliente'
    )

    respondido_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='devoluciones_respondidas',
        verbose_name='Respondido por'
    )

    fecha_en_revision = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='Fecha en revisión'
    )

    fecha_respuesta_cliente = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='Fecha respuesta cliente'
    )

    fecha_observacion_cliente = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='Fecha observación cliente'
    )

    fecha_adjuntos_cliente = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='Fecha adjuntos cliente'
    )
    fecha_aprobacion_cliente = models.DateTimeField(
    blank=True,
    null=True,
    verbose_name='Fecha aprobación cliente'
    )

    fecha_rechazo_cliente = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='Fecha rechazo cliente'
    )
    fecha_cierre = models.DateTimeField(
    blank=True,
    null=True,
    verbose_name='Fecha cierre'
    )

    cerrado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='devoluciones_cerradas',
        verbose_name='Cerrado por'
    )

    # Usuario creador del vale/devolución
    creado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='devoluciones_creadas',
        verbose_name='Creado por'
    )

    creado_en = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Creado en'
    )

    actualizado_en = models.DateTimeField(
        auto_now=True,
        verbose_name='Actualizado en'
    )

    class Meta:
        ordering = ['-fecha_recepcion', '-creado_en']
        verbose_name = 'Devolución'
        verbose_name_plural = 'Devoluciones'

    @property
    def correlativo(self):
        if self.id:
            return str(self.id).zfill(10)
        return '0000000000'
    
    @property
    def series_resumen(self):
        """
        Muestra las series asociadas en formato corto para tabla y detalle.
        Si no hay series múltiples, usa el campo antiguo serie.
        """
        try:
            series = list(self.series.values_list('serie', flat=True))
        except Exception:
            series = []

        if series:
            if len(series) <= 3:
                return ', '.join(series)

            return f'{len(series)} series: {", ".join(series[:3])}...'

        return self.serie or '-'

    def __str__(self):
        return f'{self.correlativo} - {self.numero_documento} - {self.cliente} - {self.sku}'
    
class ReturnRequestHistory(models.Model):
    return_request = models.ForeignKey(
        ReturnRequest,
        on_delete=models.CASCADE,
        related_name='historial'
    )

    titulo = models.CharField(max_length=150)

    descripcion = models.TextField(
        blank=True,
        null=True
    )

    creado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True
    )

    creado_en = models.DateTimeField(auto_now_add=True)

    tipo = models.CharField(
        max_length=50,
        blank=True,
        null=True
    )

    class Meta:
        ordering = ['creado_en']
        verbose_name = 'Historial de devolución'
        verbose_name_plural = 'Historial de devoluciones'

    def __str__(self):
        return f'{self.return_request.correlativo} - {self.titulo}'
    
class ReturnRequestAttachment(models.Model):
    TIPO_CHOICES = [
        ('DOCUMENTO_INTERNO', 'Documento interno'),
        ('FOTO_INTERNA', 'Foto interna'),
        ('DOCUMENTO_CLIENTE', 'Documento cliente'),
        ('FOTO_CLIENTE', 'Foto cliente'),
    ]

    return_request = models.ForeignKey(
        ReturnRequest,
        on_delete=models.CASCADE,
        related_name='adjuntos'
    )

    archivo = models.FileField(
        upload_to='returns/adjuntos/',
        verbose_name='Archivo'
    )

    tipo = models.CharField(
        max_length=30,
        choices=TIPO_CHOICES
    )

    subido_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True
    )

    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['creado_en']
        verbose_name = 'Adjunto devolución'
        verbose_name_plural = 'Adjuntos devoluciones'

    def __str__(self):
        return f'{self.return_request.correlativo} - {self.get_tipo_display()}'
class ReturnRequestSerial(models.Model):
    return_request = models.ForeignKey(
        ReturnRequest,
        on_delete=models.CASCADE,
        related_name='series',
        verbose_name='Devolución'
    )

    serie = models.CharField(
        max_length=150,
        verbose_name='Serie'
    )

    creado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='series_devoluciones_creadas',
        verbose_name='Creado por'
    )

    creado_en = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Creado en'
    )

    class Meta:
        ordering = ['id']
        verbose_name = 'Serie de devolución'
        verbose_name_plural = 'Series de devoluciones'
        constraints = [
            models.UniqueConstraint(
                fields=['return_request', 'serie'],
                name='unique_return_request_serie'
            )
        ]

    def __str__(self):
        return f'{self.return_request.correlativo} - {self.serie}'