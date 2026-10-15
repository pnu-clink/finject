"""Preserve the source and its comparison in execution order."""
def run(ctx, inputs, name):
    source, sample = pp01_receive_input(ctx, inputs, name)
    pp02_record_source(ctx, source)
    pp03_compare_source(ctx, source)
    return source, sample


def pp01_receive_input(ctx, inputs, name):
    source = inputs.case(name)
    sample = source['sample']
    ctx.save('01-source/01-receive-input/01-input.json', sample)
    return source, sample


def pp02_record_source(ctx, source):
    ctx.save('01-source/02-record-source/01-provenance.json', source['comparison'])


def pp03_compare_source(ctx, source):
    ctx.save('01-source/03-compare-source/01-result.json', source['comparison'])
