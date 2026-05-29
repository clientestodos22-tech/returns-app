from django import forms
from .models import ReturnRequest
from django.contrib.auth.models import User, Group

class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    widget = MultipleFileInput

    def clean(self, data, initial=None):
        single_file_clean = super().clean

        if not data:
            if self.required:
                raise forms.ValidationError(self.error_messages['required'], code='required')
            return []

        if isinstance(data, (list, tuple)):
            return [single_file_clean(file, initial) for file in data]

        return [single_file_clean(data, initial)]

class ReturnRequestForm(forms.ModelForm):
    documentos_adjuntos = MultipleFileField(
        label='Documentos adjuntos',
        required=False,
        widget=MultipleFileInput(attrs={
            'class': 'form-control',
            'multiple': True
        })
    )

    fotos_evidencia = MultipleFileField(
        label='Fotos evidencia',
        required=False,
        widget=MultipleFileInput(attrs={
            'class': 'form-control',
            'multiple': True,
            'accept': 'image/*'
        })
    )
    class Meta:
        model = ReturnRequest
        fields = [
            'fecha_recepcion',
            'numero_documento',
            'documento_ingreso',
            'cliente',
            'sku',
            'cantidad',
            'codigo_numerico',
            'serie',
            'ubicacion',
            'numero_dcto_estado',
            'observaciones',
        ]

        labels = {
            'fecha_recepcion': 'Fecha Recepción',
            'numero_documento': 'N° Documento',
            'documento_ingreso': 'Documento de ingreso / NC cliente',
            'cliente': 'Cliente',
            'sku': 'SKU',
            'cantidad': 'Cantidad',
            'codigo_numerico': 'Código Numérico',
            'serie': 'Serie',
            'ubicacion': 'Ubicación',
            'numero_dcto_estado': 'Estado de Inventario',
            'estado': 'Estado',
            'documento_adjunto': 'Documento adjunto',
            'foto_evidencia': 'Foto evidencia',
            'observaciones': 'Observaciones',
        }

        widgets = {
            'fecha_recepcion': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'numero_documento': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: 213'
            }),
            'documento_ingreso': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'NC generada por el cliente'
            }),
            'cliente': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre del cliente'
            }),
            'sku': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Código SKU'
            }),
            'cantidad': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1'
            }),
            'codigo_numerico': forms.TextInput(attrs={
                'class': 'form-control'
            }),
            'serie': forms.TextInput(attrs={
                'class': 'form-control'
            }),
            'ubicacion': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: PAD-022-001'
            }),
            'numero_dcto_estado': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: CL08, CL01, CL05...'
            }),
            'estado': forms.Select(attrs={
                'class': 'form-select'
            }),
            'documento_adjunto': forms.FileInput(attrs={
                'class': 'form-control'
            }),
            'foto_evidencia': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
            'observaciones': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Comentarios, condición del producto, motivo de devolución...'
            }),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        es_admin = False

        if self.user:
            es_admin = self.user.is_staff or self.user.is_superuser

        if es_admin:
            self.fields['documento_ingreso'].required = False
            self.fields['documento_ingreso'].widget.attrs.pop('required', None)
            self.fields['documento_ingreso'].widget.attrs['placeholder'] = 'Opcional para administrador'
        else:
            self.fields['documento_ingreso'].required = True
            self.fields['documento_ingreso'].widget.attrs['required'] = 'required'
            self.fields['documento_ingreso'].widget.attrs['placeholder'] = 'Obligatorio para cliente'

    def clean_documento_ingreso(self):
        documento_ingreso = self.cleaned_data.get('documento_ingreso')

        es_admin = False

        if self.user:
            es_admin = self.user.is_staff or self.user.is_superuser

        if not es_admin and not documento_ingreso:
            raise forms.ValidationError(
                'El documento de ingreso / NC cliente es obligatorio para usuarios cliente.'
            )

        return documento_ingreso


class ReturnClientResponseForm(forms.ModelForm):
    class Meta:
        model = ReturnRequest
        fields = [
            'documento_ingreso',
            'numero_dcto_estado',
            'respuesta_cliente',
            'documento_respuesta_cliente',
            'foto_respuesta_cliente',
        ]

        labels = {
            'documento_ingreso': 'Documento de ingreso / NC cliente',
            'numero_dcto_estado': 'Estado de Inventario',
            'respuesta_cliente': 'Observaciones',
            'documento_respuesta_cliente': 'Documento adjunto',
            'foto_respuesta_cliente': 'Foto evidencia',
        }

        widgets = {
            'documento_ingreso': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ingrese NC o documento generado por el cliente',
            }),
            'numero_dcto_estado': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: CL08, CL05, Disponible, Bloqueado...'
            }),
            'respuesta_cliente': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Ingrese observaciones de esta respuesta...',
            }),
            'documento_respuesta_cliente': forms.FileInput(attrs={
                'class': 'form-control'
            }),
            'foto_respuesta_cliente': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
        }

    def clean_documento_ingreso(self):
        documento = self.cleaned_data.get('documento_ingreso')

        if not documento:
            raise forms.ValidationError('Debe ingresar el documento de ingreso / NC cliente.')

        return documento

    def clean_respuesta_cliente(self):
        respuesta = self.cleaned_data.get('respuesta_cliente')

        if not respuesta:
            raise forms.ValidationError('Debe ingresar una observación.')

        return respuesta
class ClienteUserCreateForm(forms.Form):
    username = forms.CharField(
        label='Usuario',
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ej: cliente_Intsan'
        })
    )

    first_name = forms.CharField(
        label='Nombre cliente',
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ej: Intsan'
        })
    )

    email = forms.EmailField(
        label='Correo',
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'cliente@empresa.com'
        })
    )

    password1 = forms.CharField(
        label='Contraseña',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ingrese contraseña'
        })
    )

    password2 = forms.CharField(
        label='Confirmar contraseña',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Repita la contraseña'
        })
    )

    def clean_username(self):
        username = self.cleaned_data.get('username')

        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('Ya existe un usuario con este nombre.')

        return username

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')

        if password1 and password2 and password1 != password2:
            raise forms.ValidationError('Las contraseñas no coinciden.')

        return cleaned_data

    def save(self):
        grupo_cliente, creado = Group.objects.get_or_create(name='Cliente')

        usuario = User.objects.create_user(
            username=self.cleaned_data['username'],
            password=self.cleaned_data['password1'],
            first_name=self.cleaned_data['first_name'],
            email=self.cleaned_data.get('email') or ''
        )

        usuario.groups.add(grupo_cliente)
        usuario.is_staff = False
        usuario.is_superuser = False
        usuario.save()

        return usuario