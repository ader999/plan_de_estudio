from django import template

register = template.Library()

@register.filter(name='get_attribute')
def get_attribute(obj, arg):
    """
    Filtro para obtener un atributo de un objeto dinámicamente.
    Uso: {{ my_object|get_attribute:"attribute_name" }}
    O, para atributos dinámicos: {{ my_object|get_attribute:variable_with_name }}
    """
    # Dividir el argumento en la base del atributo y el sufijo dinámico
    parts = arg.rsplit('_', 1)
    if len(parts) == 2:
        base_attr, suffix = parts
        # Reconstruir el nombre del atributo
        attr_name = f"{base_attr}_{suffix}"
        return getattr(obj, attr_name, None)
    return getattr(obj, arg, None)