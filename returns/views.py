from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.utils import timezone
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.urls import reverse

from .models import ReturnRequest, ReturnRequestHistory, ReturnRequestAttachment
from .forms import ReturnRequestForm, ReturnClientResponseForm, ClienteUserCreateForm


def es_cliente(user):
    """
    Retorna True si el usuario pertenece al grupo Cliente.
    """
    return user.is_authenticated and user.groups.filter(name='Cliente').exists()


def nombre_responsable_usuario(user):
    """
    Devuelve nombre completo si existe, si no devuelve username.
    """
    nombre = user.get_full_name()
    return nombre if nombre else user.username

def valor_legible(valor):
    if valor is None or valor == '':
        return 'vacío'
    return str(valor)


def registrar_historial(devolucion, titulo, descripcion, usuario=None, tipo=None):
    ReturnRequestHistory.objects.create(
        return_request=devolucion,
        titulo=titulo,
        descripcion=descripcion,
        creado_por=usuario if usuario and usuario.is_authenticated else None,
        tipo=tipo
    )


def registrar_cambio_si_corresponde(devolucion, campo_nombre, etiqueta, valor_anterior, valor_nuevo, usuario):
    anterior = valor_legible(valor_anterior)
    nuevo = valor_legible(valor_nuevo)

    if anterior != nuevo:
        registrar_historial(
            devolucion=devolucion,
            titulo=f'{etiqueta} actualizado',
            descripcion=f'{etiqueta}: {anterior} → {nuevo}',
            usuario=usuario,
            tipo='CAMBIO_CLIENTE'
        )

def guardar_adjuntos_internos(devolucion, request):
    documentos = request.FILES.getlist('documentos_adjuntos')
    fotos = request.FILES.getlist('fotos_evidencia')

    total_documentos = 0
    total_fotos = 0

    for archivo in documentos:
        ReturnRequestAttachment.objects.create(
            return_request=devolucion,
            archivo=archivo,
            tipo='DOCUMENTO_INTERNO',
            subido_por=request.user
        )
        total_documentos += 1

    for archivo in fotos:
        ReturnRequestAttachment.objects.create(
            return_request=devolucion,
            archivo=archivo,
            tipo='FOTO_INTERNA',
            subido_por=request.user
        )
        total_fotos += 1

    if total_documentos or total_fotos:
        registrar_historial(
            devolucion=devolucion,
            titulo='Adjuntos internos cargados',
            descripcion=f'Se cargaron {total_documentos} documento(s) y {total_fotos} foto(s) internas.',
            usuario=request.user,
            tipo='ADJUNTOS_INTERNOS'
        )

def archivo_data(archivo, titulo, tipo):
    """
    Convierte un FileField/ImageField en una estructura segura para el frontend.
    """
    if not archivo:
        return None

    try:
        url = archivo.url
    except Exception:
        return None

    nombre = archivo.name.split('/')[-1] if getattr(archivo, 'name', '') else titulo

    return {
        'titulo': titulo,
        'nombre': nombre,
        'url': url,
        'tipo': tipo,
    }


def obtener_galeria_devolucion(devolucion):
    """
    Devuelve todos los documentos y fotos asociados a una devolución,
    tanto de campos antiguos como del modelo de adjuntos múltiples.
    """
    galeria = []

    archivos_principales = [
        ('documento_adjunto', 'Documento interno', 'document'),
        ('foto_evidencia', 'Foto interna', 'image'),
        ('documento_respuesta_cliente', 'Documento cliente', 'document'),
        ('foto_respuesta_cliente', 'Foto cliente', 'image'),
    ]

    for campo, titulo, tipo in archivos_principales:
        archivo = getattr(devolucion, campo, None)
        data = archivo_data(archivo, titulo, tipo)
        if data:
            galeria.append(data)

    if hasattr(devolucion, 'adjuntos'):
        for adjunto in devolucion.adjuntos.all().order_by('creado_en', 'id'):
            archivo = getattr(adjunto, 'archivo', None)
            tipo_adjunto = getattr(adjunto, 'tipo', '') or ''

            if not archivo:
                continue

            tipo_upper = tipo_adjunto.upper()
            es_foto = 'FOTO' in tipo_upper or 'IMAGE' in tipo_upper

            if 'CLIENTE' in tipo_upper:
                titulo = 'Foto cliente' if es_foto else 'Documento cliente'
            else:
                titulo = 'Foto interna' if es_foto else 'Documento interno'

            data = archivo_data(
                archivo,
                titulo,
                'image' if es_foto else 'document'
            )

            if data:
                galeria.append(data)

    return galeria


def redirect_after_action(request, devolucion):
    next_url = request.POST.get('next') or request.GET.get('next')

    if next_url:
        return redirect(next_url)

    return redirect('returns:return_detail', pk=devolucion.pk)

@login_required
def return_list(request):
    query = request.GET.get('q', '').strip()
    estado = request.GET.get('estado', '').strip()

    base_queryset = ReturnRequest.objects.all()
    devoluciones = base_queryset

    if query:
        devoluciones = devoluciones.filter(
            Q(numero_documento__icontains=query) |
            Q(documento_ingreso__icontains=query) |
            Q(cliente__icontains=query) |
            Q(sku__icontains=query) |
            Q(codigo_numerico__icontains=query) |
            Q(serie__icontains=query) |
            Q(ubicacion__icontains=query) |
            Q(numero_dcto_estado__icontains=query) |
            Q(responsable__icontains=query)
        )

    if estado:
        devoluciones = devoluciones.filter(estado=estado)

    cliente = es_cliente(request.user)

    return render(request, 'returns/return_list.html', {
        'devoluciones': devoluciones,
        'query': query,
        'estado': estado,
        'estado_choices': ReturnRequest.ESTADO_CHOICES,

        'form': ReturnRequestForm(user=request.user),
        'user_form': ClienteUserCreateForm(),

        'open_user_modal': False,
        'es_cliente': cliente,

        'total_devoluciones': base_queryset.count(),
        'total_recibidas': base_queryset.filter(estado='RECIBIDO').count(),
        'total_revision': base_queryset.filter(estado='EN_REVISION').count(),
        'total_observadas': base_queryset.filter(estado='OBSERVADO').count(),
        'total_aprobadas': base_queryset.filter(estado='APROBADO').count(),
        'total_rechazadas': base_queryset.filter(estado='RECHAZADO').count(),
        'total_cerradas': base_queryset.filter(estado='CERRADO').count(),
        'total_filtradas': devoluciones.count(),
    })


@login_required
def return_create(request):
    if es_cliente(request.user):
        raise PermissionDenied

    if request.method == 'POST':
        form = ReturnRequestForm(request.POST, request.FILES, user=request.user)

        if form.is_valid():
            devolucion = form.save(commit=False)
            devolucion.estado = 'RECIBIDO'
            devolucion.creado_por = request.user
            devolucion.responsable = nombre_responsable_usuario(request.user)
            devolucion.save()

            guardar_adjuntos_internos(devolucion, request)

            messages.success(request, 'Devolución registrada correctamente.')
            return redirect('returns:return_list')
    else:
        form = ReturnRequestForm(user=request.user)

    return render(request, 'returns/return_form.html', {
        'form': form,
        'title': 'Registrar devolución',
        'es_cliente': es_cliente(request.user),
    })


@login_required
def return_detail(request, pk):
    devolucion = get_object_or_404(ReturnRequest, pk=pk)
    cliente = es_cliente(request.user)

    if cliente and devolucion.estado == 'RECIBIDO':
        ahora = timezone.now()

        devolucion.estado = 'EN_REVISION'

        if not devolucion.fecha_en_revision:
            devolucion.fecha_en_revision = ahora

        devolucion.save(update_fields=[
            'estado',
            'fecha_en_revision',
            'actualizado_en'
        ])

        registrar_historial(
            devolucion=devolucion,
            titulo='Estado actualizado',
            descripcion='Estado: Recibido → En revisión',
            usuario=request.user,
            tipo='EN_REVISION'
        )

    return render(request, 'returns/return_detail.html', {
        'devolucion': devolucion,
        'es_cliente': cliente,
        'response_form': ReturnClientResponseForm(instance=devolucion,initial={'respuesta_cliente': ''}),
        'historial_extra': devolucion.historial.all(),
        'documentos_internos': devolucion.adjuntos.filter(tipo='DOCUMENTO_INTERNO'),
        'fotos_internas': devolucion.adjuntos.filter(tipo='FOTO_INTERNA'),
    })


@login_required
def return_update(request, pk):
    """
    El usuario Cliente no puede editar la devolución completa.
    Solo puede responder.
    """
    if es_cliente(request.user):
        raise PermissionDenied

    devolucion = get_object_or_404(ReturnRequest, pk=pk)

    if devolucion.estado in ['APROBADO', 'RECHAZADO', 'CERRADO']:
        messages.warning(request, 'Esta devolución ya tiene un estado final y no puede editarse.')
        return redirect_after_action(request, devolucion)

    if request.method == 'POST':
        form = ReturnRequestForm(
            request.POST,
            request.FILES,
            instance=devolucion,
            user=request.user
        )

        if form.is_valid():
            form.save()
            messages.success(request, 'Devolución actualizada correctamente.')
            return redirect_after_action(request, devolucion)
    else:
        form = ReturnRequestForm(instance=devolucion, user=request.user)

    return render(request, 'returns/return_form.html', {
        'form': form,
        'title': 'Editar devolución',
        'devolucion': devolucion,
        'es_cliente': es_cliente(request.user),
    })


@login_required
def return_respond(request, pk):
    devolucion = get_object_or_404(ReturnRequest, pk=pk)

    if not es_cliente(request.user):
        raise PermissionDenied

    if devolucion.estado in ['APROBADO', 'RECHAZADO', 'CERRADO']:
        messages.warning(request, 'Esta devolución ya tiene un estado final.')
        return redirect_after_action(request, devolucion)

    if request.method == 'POST':
        documento_ingreso_anterior = devolucion.documento_ingreso
        estado_inventario_anterior = devolucion.numero_dcto_estado

        documento_cliente_anterior = (
            devolucion.documento_respuesta_cliente.name
            if devolucion.documento_respuesta_cliente else ''
        )

        foto_cliente_anterior = (
            devolucion.foto_respuesta_cliente.name
            if devolucion.foto_respuesta_cliente else ''
        )

        form = ReturnClientResponseForm(
            request.POST,
            request.FILES,
            instance=devolucion
        )

        if form.is_valid():
            respuesta = form.save(commit=False)
            ahora = timezone.now()

            observacion_nueva = form.cleaned_data.get('respuesta_cliente') or ''
            observacion_nueva = observacion_nueva.strip()

            respuesta.estado = 'APROBADO'
            respuesta.respondido_por = request.user
            respuesta.fecha_respuesta_cliente = ahora
            respuesta.fecha_aprobacion_cliente = ahora
            respuesta.respuesta_cliente = observacion_nueva

            if not respuesta.fecha_en_revision:
                respuesta.fecha_en_revision = ahora

            if observacion_nueva:
                respuesta.fecha_observacion_cliente = ahora

            if (
                request.FILES.get('documento_respuesta_cliente') or
                request.FILES.get('foto_respuesta_cliente')
            ):
                respuesta.fecha_adjuntos_cliente = ahora

            respuesta.save()

            # 1) Registrar siempre la respuesta enviada como evento independiente
            if observacion_nueva:
                descripcion_respuesta = f'El cliente envió respuesta. Observación: {observacion_nueva}'
            else:
                descripcion_respuesta = 'El cliente envió respuesta sin observaciones adicionales.'

            registrar_historial(
                devolucion=respuesta,
                titulo='Respuesta enviada por cliente',
                descripcion=descripcion_respuesta,
                usuario=request.user,
                tipo='RESPUESTA_CLIENTE'
            )

            # 2) Registrar cambios de campos si hubo cambios
            registrar_cambio_si_corresponde(
                respuesta,
                'documento_ingreso',
                'Documento de ingreso / NC cliente',
                documento_ingreso_anterior,
                respuesta.documento_ingreso,
                request.user
            )

            registrar_cambio_si_corresponde(
                respuesta,
                'numero_dcto_estado',
                'Estado de Inventario',
                estado_inventario_anterior,
                respuesta.numero_dcto_estado,
                request.user
            )

            documento_cliente_nuevo = (
                respuesta.documento_respuesta_cliente.name
                if respuesta.documento_respuesta_cliente else ''
            )

            foto_cliente_nueva = (
                respuesta.foto_respuesta_cliente.name
                if respuesta.foto_respuesta_cliente else ''
            )

            registrar_cambio_si_corresponde(
                respuesta,
                'documento_respuesta_cliente',
                'Documento adjunto cliente',
                documento_cliente_anterior,
                documento_cliente_nuevo,
                request.user
            )

            registrar_cambio_si_corresponde(
                respuesta,
                'foto_respuesta_cliente',
                'Foto evidencia cliente',
                foto_cliente_anterior,
                foto_cliente_nueva,
                request.user
            )

            # 3) Registrar aprobación como evento independiente
            registrar_historial(
                devolucion=respuesta,
                titulo='Devolución aprobada',
                descripcion='El cliente aprobó la devolución.',
                usuario=request.user,
                tipo='APROBADO'
            )

            messages.success(request, 'Devolución aprobada correctamente.')
            return redirect_after_action(request, devolucion)

    messages.error(request, 'No se pudo registrar la respuesta. Revise los campos.')
    return redirect_after_action(request, devolucion)

@login_required
def return_reject(request, pk):
    devolucion = get_object_or_404(ReturnRequest, pk=pk)

    if not es_cliente(request.user):
        raise PermissionDenied

    if devolucion.estado in ['APROBADO', 'RECHAZADO', 'CERRADO']:
        messages.warning(request, 'Esta devolución ya tiene un estado final.')
        return redirect_after_action(request, devolucion)

    if request.method == 'POST':
        motivo_rechazo = request.POST.get('motivo_rechazo', '').strip()
        ahora = timezone.now()

        observacion_anterior = devolucion.respuesta_cliente

        devolucion.estado = 'RECHAZADO'
        devolucion.respondido_por = request.user
        devolucion.fecha_respuesta_cliente = ahora
        devolucion.fecha_rechazo_cliente = ahora

        if not devolucion.fecha_en_revision:
            devolucion.fecha_en_revision = ahora

        if motivo_rechazo:
            devolucion.respuesta_cliente = motivo_rechazo
            devolucion.fecha_observacion_cliente = ahora

        devolucion.save()

        registrar_cambio_si_corresponde(
            devolucion,
            'respuesta_cliente',
            'Motivo de rechazo',
            observacion_anterior,
            devolucion.respuesta_cliente,
            request.user
        )

        registrar_historial(
            devolucion=devolucion,
            titulo='Devolución rechazada',
            descripcion='El cliente rechazó la devolución.',
            usuario=request.user,
            tipo='RECHAZADO'
        )

        messages.success(request, 'Devolución rechazada correctamente.')
        return redirect_after_action(request, devolucion)

    return redirect_after_action(request, devolucion)
@login_required
def return_observe(request, pk):
    devolucion = get_object_or_404(ReturnRequest, pk=pk)

    if not es_cliente(request.user):
        raise PermissionDenied

    if devolucion.estado in ['APROBADO', 'RECHAZADO', 'CERRADO']:
        messages.warning(request, 'Esta devolución ya tiene un estado final.')
        return redirect_after_action(request, devolucion)

    if request.method == 'POST':
        observacion = request.POST.get('observacion_cliente', '').strip()

        if not observacion:
            messages.error(request, 'Debe ingresar una observación para solicitar la corrección.')
            return redirect_after_action(request, devolucion)

        ahora = timezone.now()
        estado_anterior = devolucion.get_estado_display()

        devolucion.estado = 'OBSERVADO'
        devolucion.respuesta_cliente = observacion
        devolucion.respondido_por = request.user
        devolucion.fecha_observacion_cliente = ahora

        if not devolucion.fecha_en_revision:
            devolucion.fecha_en_revision = ahora

        devolucion.save(update_fields=[
            'estado',
            'respuesta_cliente',
            'respondido_por',
            'fecha_observacion_cliente',
            'fecha_en_revision',
            'actualizado_en',
        ])

        registrar_historial(
            devolucion=devolucion,
            titulo='Corrección solicitada por cliente',
            descripcion=f'Estado: {estado_anterior} → Pendiente corrección. Observación: {observacion}',
            usuario=request.user,
            tipo='OBSERVADO'
        )

        messages.success(request, 'Solicitud de corrección enviada correctamente.')
        return redirect_after_action(request, devolucion)

    return redirect_after_action(request, devolucion)


@login_required
def return_send_review(request, pk):
    devolucion = get_object_or_404(ReturnRequest, pk=pk)

    if es_cliente(request.user):
        raise PermissionDenied

    if devolucion.estado != 'OBSERVADO':
        messages.warning(request, 'Solo puedes enviar a revisión una devolución pendiente de corrección.')
        return redirect_after_action(request, devolucion)

    if request.method == 'POST':
        ahora = timezone.now()

        devolucion.estado = 'EN_REVISION'
        devolucion.fecha_en_revision = ahora
        devolucion.save(update_fields=[
            'estado',
            'fecha_en_revision',
            'actualizado_en',
        ])

        registrar_historial(
            devolucion=devolucion,
            titulo='Corrección enviada a revisión',
            descripcion='El administrador realizó la corrección y envió la devolución nuevamente a revisión del cliente.',
            usuario=request.user,
            tipo='EN_REVISION'
        )

        messages.success(request, 'Devolución enviada nuevamente a revisión.')
        return redirect_after_action(request, devolucion)

    return redirect_after_action(request, devolucion)

@login_required
def return_close(request, pk):
    devolucion = get_object_or_404(ReturnRequest, pk=pk)

    if es_cliente(request.user):
        raise PermissionDenied

    if devolucion.estado != 'APROBADO':
        messages.warning(request, 'Solo se pueden cerrar devoluciones aprobadas.')
        return redirect_after_action(request, devolucion)

    if request.method == 'POST':
        ahora = timezone.now()

        devolucion.estado = 'CERRADO'
        devolucion.fecha_cierre = ahora
        devolucion.cerrado_por = request.user
        devolucion.save(update_fields=[
            'estado',
            'fecha_cierre',
            'cerrado_por',
            'actualizado_en',
        ])

        registrar_historial(
            devolucion=devolucion,
            titulo='Devolución cerrada',
            descripcion='La devolución fue cerrada. Caso ingresado y finalizado en WMS.',
            usuario=request.user,
            tipo='CERRADO'
        )

        messages.success(request, 'Devolución cerrada correctamente.')
        return redirect_after_action(request, devolucion)

    return redirect_after_action(request, devolucion)

@login_required
def user_create(request):
    if not request.user.is_staff and not request.user.is_superuser:
        raise PermissionDenied

    if request.method == 'POST':
        form_usuario = ClienteUserCreateForm(request.POST)

        if form_usuario.is_valid():
            usuario = form_usuario.save()
            messages.success(
                request,
                f'Usuario cliente "{usuario.username}" creado correctamente.'
            )
            return redirect('returns:return_list')

        query = request.GET.get('q', '').strip()
        estado = request.GET.get('estado', '').strip()

        base_queryset = ReturnRequest.objects.all()
        devoluciones = base_queryset

        if query:
            devoluciones = devoluciones.filter(
                Q(numero_documento__icontains=query) |
                Q(documento_ingreso__icontains=query) |
                Q(cliente__icontains=query) |
                Q(sku__icontains=query) |
                Q(codigo_numerico__icontains=query) |
                Q(serie__icontains=query) |
                Q(ubicacion__icontains=query) |
                Q(numero_dcto_estado__icontains=query) |
                Q(responsable__icontains=query)
            )

        if estado:
            devoluciones = devoluciones.filter(estado=estado)

        return render(request, 'returns/return_list.html', {
            'devoluciones': devoluciones,
            'query': query,
            'estado': estado,
            'estado_choices': ReturnRequest.ESTADO_CHOICES,

            'form': ReturnRequestForm(user=request.user),
            'user_form': form_usuario,

            'open_user_modal': True,
            'es_cliente': es_cliente(request.user),

            'total_devoluciones': base_queryset.count(),
            'total_recibidas': base_queryset.filter(estado='RECIBIDO').count(),
            'total_revision': base_queryset.filter(estado='EN_REVISION').count(),
            'total_observadas': base_queryset.filter(estado='OBSERVADO').count(),
            'total_aprobadas': base_queryset.filter(estado='APROBADO').count(),
            'total_rechazadas': base_queryset.filter(estado='RECHAZADO').count(),
            'total_cerradas': base_queryset.filter(estado='CERRADO').count(),
            'total_filtradas': devoluciones.count(),
        })

    return redirect('returns:return_list')

@login_required
def return_status_feed(request):
    devoluciones = ReturnRequest.objects.all()

    data = []

    for item in devoluciones:
        data.append({
            'id': item.id,
            'estado': item.estado,
            'estado_display': item.get_estado_display(),
        })

    payload = {
        'items': data,
        'counts': {
            'total': devoluciones.count(),
            'recibidas': devoluciones.filter(estado='RECIBIDO').count(),
            'revision': devoluciones.filter(estado='EN_REVISION').count(),
            'observadas': devoluciones.filter(estado='OBSERVADO').count(),
            'aprobadas': devoluciones.filter(estado='APROBADO').count(),
            'rechazadas': devoluciones.filter(estado='RECHAZADO').count(),
            'cerradas': devoluciones.filter(estado='CERRADO').count(),
        }
    }

    return JsonResponse(payload)

@login_required
def return_live_feed(request):
    query = request.GET.get('q', '').strip()
    estado = request.GET.get('estado', '').strip()

    base_queryset = ReturnRequest.objects.all()
    devoluciones = base_queryset

    if query:
        devoluciones = devoluciones.filter(
            Q(numero_documento__icontains=query) |
            Q(documento_ingreso__icontains=query) |
            Q(cliente__icontains=query) |
            Q(sku__icontains=query) |
            Q(codigo_numerico__icontains=query) |
            Q(serie__icontains=query) |
            Q(ubicacion__icontains=query) |
            Q(numero_dcto_estado__icontains=query) |
            Q(responsable__icontains=query)
        )

    if estado:
        devoluciones = devoluciones.filter(estado=estado)

    cliente = es_cliente(request.user)

    items = []

    for item in devoluciones:
        items.append({
            'id': item.id,
            'correlativo': item.correlativo,
            'fecha_recepcion': item.fecha_recepcion.strftime('%b %d, %Y'),
            'numero_documento': item.numero_documento or '',
            'documento_ingreso': item.documento_ingreso or 'None',
            'cliente': item.cliente or '',
            'sku': item.sku or '',
            'cantidad': item.cantidad,
            'serie': item.serie or '-',
            'estado_inventario': item.numero_dcto_estado or '-',
            'responsable': item.responsable or '-',
            'estado': item.estado,
            'estado_display': item.get_estado_display(),
            'detail_url': reverse('returns:return_detail', args=[item.pk]),
            'edit_url': reverse('returns:return_update', args=[item.pk]),
            'is_cliente': cliente,
            'respond_url': reverse('returns:return_respond', args=[item.pk]),
            'observe_url': reverse('returns:return_observe', args=[item.pk]),
            'reject_url': reverse('returns:return_reject', args=[item.pk]),
            'close_url': reverse('returns:return_close', args=[item.pk]),
            'send_review_url': reverse('returns:return_send_review', args=[item.pk]),
            'update_url': reverse('returns:return_update', args=[item.pk]),
            'timeline_url': reverse('returns:return_timeline_feed', args=[item.pk]),
            'fecha_iso': item.fecha_recepcion.strftime('%Y-%m-%d'),
            'codigo_numerico': item.codigo_numerico or '',
            'ubicacion': item.ubicacion or '',
            'observaciones': item.observaciones or '',
            'galeria': obtener_galeria_devolucion(item),
        })

    return JsonResponse({
        'items': items,
        'counts': {
            'total': base_queryset.count(),
            'recibidas': base_queryset.filter(estado='RECIBIDO').count(),
            'revision': base_queryset.filter(estado='EN_REVISION').count(),
            'observadas': base_queryset.filter(estado='OBSERVADO').count(),
            'aprobadas': base_queryset.filter(estado='APROBADO').count(),
            'rechazadas': base_queryset.filter(estado='RECHAZADO').count(),
            'cerradas': base_queryset.filter(estado='CERRADO').count(),
            'filtradas': devoluciones.count(),
        }
    })

@login_required
def return_timeline_feed(request, pk):
    devolucion = get_object_or_404(ReturnRequest, pk=pk)

    def format_date(value):
        if not value:
            return 'Pendiente'
        return timezone.localtime(value).strftime('%d/%m/%Y %H:%M')

    def user_label(user):
        if not user:
            return 'Sistema'
        return user.get_full_name() or user.username

    def icon_by_type(tipo):
        icons = {
            'CREACION': 'bi-plus-circle',
            'EN_REVISION': 'bi-eye',
            'OBSERVADO': 'bi-chat-square-text',
            'RESPUESTA_CLIENTE': 'bi-send',
            'CAMBIO_CLIENTE': 'bi-pencil-square',
            'APROBADO': 'bi-check-circle',
            'RECHAZADO': 'bi-x-circle',
            'CERRADO': 'bi-lock',
        }
        return icons.get(tipo, 'bi-clock-history')

    def color_by_type(tipo):
        if tipo in ['APROBADO', 'CERRADO']:
            return 'success'
        if tipo == 'RECHAZADO':
            return 'danger'
        if tipo in ['OBSERVADO', 'EN_REVISION']:
            return 'warning'
        return 'primary'

    items = []

    items.append({
        'tipo': 'CREACION',
        'titulo': 'Creación de devolución',
        'descripcion': f'Devolución creada por {devolucion.responsable or "Sistema"}.',
        'fecha': format_date(devolucion.creado_en),
        'usuario': user_label(devolucion.creado_por) if devolucion.creado_por else devolucion.responsable or 'Sistema',
        'icon': icon_by_type('CREACION'),
        'color': color_by_type('CREACION'),
    })

    for item in devolucion.historial.all().order_by('creado_en', 'id'):
        items.append({
            'tipo': item.tipo,
            'titulo': item.titulo,
            'descripcion': item.descripcion,
            'fecha': format_date(item.creado_en),
            'usuario': user_label(item.creado_por),
            'icon': icon_by_type(item.tipo),
            'color': color_by_type(item.tipo),
        })

    return JsonResponse({
        'id': devolucion.id,
        'correlativo': devolucion.correlativo,
        'items': items,
    })