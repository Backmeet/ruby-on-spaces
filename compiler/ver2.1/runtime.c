#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

typedef enum {
    VAL_NULL, VAL_INT, VAL_FLOAT, VAL_STRING, VAL_LIST,
    VAL_DICT, VAL_CLASS, VAL_FUNCTION, VAL_POINTER
} ValueTag;

typedef struct Value Value;

typedef struct {
    Value* items;
    size_t len;
    size_t cap;
} List;

typedef struct {
    char** keys;
    Value* values;
    size_t len;
    size_t cap;
} Dict;

typedef struct {
    Value* fields;
    size_t len;
} Class;

typedef Value (*FnPtr)(Value* args, int argc);

struct Value {
    ValueTag tag;
    union {
        int as_int;
        double as_float;
        char* as_str;
        List as_list;
        Dict as_dict;
        Class as_class;
        FnPtr as_fn;
        Value* as_ptr;
    };
};

/* === Constructors === */
Value val_null() {
    Value v; v.tag = VAL_NULL; return v;
}
Value val_int(int x) {
    Value v; v.tag = VAL_INT; v.as_int = x; return v;
}
Value val_float(double x) {
    Value v; v.tag = VAL_FLOAT; v.as_float = x; return v;
}
Value val_str(const char* s) {
    Value v; v.tag = VAL_STRING; v.as_str = strdup(s); return v;
}

/* === Printing === */
void print_val(Value v) {
    switch (v.tag) {
        case VAL_INT: printf("%d\n", v.as_int); break;
        case VAL_FLOAT: printf("%f\n", v.as_float); break;
        case VAL_STRING: printf("%s\n", v.as_str); break;
        case VAL_NULL: printf("null\n"); break;
        default: printf("<complex>\n"); break;
    }
}

/* === Call helper === */
Value val_call(Value fn, Value* args, int argc) {
    if (fn.tag == VAL_FUNCTION) return fn.as_fn(args, argc);
    fprintf(stderr, "TypeError: not a function\n");
    return val_null();
}

/* === Built-in functions === */
Value builtin_print(Value* args, int argc) {
    for (int i = 0; i < argc; i++) print_val(args[i]);
    return val_null();
}

Value builtin_delay(Value* args, int argc) {
    if (argc < 1) return val_null();
    double sec = (args[0].tag == VAL_INT) ? args[0].as_int : args[0].as_float;
    struct timespec ts;
    ts.tv_sec = (time_t)sec;
    ts.tv_nsec = (long)((sec - ts.tv_sec) * 1e9);
    nanosleep(&ts, NULL);
    return val_null();
}

Value builtin_range(Value* args, int argc) {
    int start = 0, end = 0, step = 1;
    if (argc == 1) { end = args[0].as_int; }
    else if (argc == 2) { start = args[0].as_int; end = args[1].as_int; }
    else if (argc == 3) { start = args[0].as_int; end = args[1].as_int; step = args[2].as_int; }

    List list = { .items = malloc(sizeof(Value) * ((end - start + step - 1) / step)), .len = 0, .cap = (end - start + step - 1) / step };
    for (int i = start; (step > 0 ? i < end : i > end); i += step)
        list.items[list.len++] = val_int(i);

    Value v; v.tag = VAL_LIST; v.as_list = list; return v;
}

static char* _strndup(const char* s, size_t n) {
    char* out = (char*)malloc(n + 1);
    if (!out) return NULL;
    memcpy(out, s, n);
    out[n] = '\0';
    return out;
}

Value builtin_subS(Value* args, int argc) {
    if (argc < 3 || args[0].tag != VAL_STRING) return val_null();
    char* s = args[0].as_str;
    int i = args[1].as_int, j = args[2].as_int;
    if (i < 0) i = 0; if (j > (int)strlen(s)) j = strlen(s);
    char* sub = _strndup(s + i, j - i);
    return val_str(sub);
}

Value builtin_subL(Value* args, int argc) {
    if (argc < 3 || args[0].tag != VAL_LIST) return val_null();
    List lst = args[0].as_list;
    int i = args[1].as_int, j = args[2].as_int;
    if (i < 0) i = 0; if (j > (int)lst.len) j = lst.len;
    List sub = { .items = malloc(sizeof(Value) * (j - i)), .len = j - i, .cap = j - i };
    memcpy(sub.items, &lst.items[i], sizeof(Value) * (j - i));
    Value v; v.tag = VAL_LIST; v.as_list = sub; return v;
}

Value builtin_cast(Value* args, int argc) {
    if (argc < 2 || args[1].tag != VAL_STRING) return val_null();
    Value x = args[0]; char* type = args[1].as_str;

    if (strcmp(type, "int") == 0) {
        if (x.tag == VAL_FLOAT) return val_int((int)x.as_float);
        if (x.tag == VAL_STRING) return val_int(atoi(x.as_str));
        if (x.tag == VAL_INT) return x;
    }
    if (strcmp(type, "float") == 0) {
        if (x.tag == VAL_INT) return val_float((double)x.as_int);
        if (x.tag == VAL_STRING) return val_float(atof(x.as_str));
        if (x.tag == VAL_FLOAT) return x;
    }
    if (strcmp(type, "string") == 0) {
        char buf[64];
        if (x.tag == VAL_INT) { snprintf(buf, 64, "%d", x.as_int); return val_str(buf); }
        if (x.tag == VAL_FLOAT) { snprintf(buf, 64, "%f", x.as_float); return val_str(buf); }
        if (x.tag == VAL_STRING) return x;
    }
    return val_null();
}

Value builtin_free(Value* args, int argc) {
    if (argc < 1) return val_null();
    Value x = args[0];
    if (x.tag == VAL_STRING) free(x.as_str);
    if (x.tag == VAL_LIST) free(x.as_list.items);
    if (x.tag == VAL_DICT) { free(x.as_dict.keys); free(x.as_dict.values); }
    if (x.tag == VAL_CLASS) free(x.as_class.fields);
    return val_null();
}

/* === Globals for builtins === */
Value print, delay, range_fn, subS, subL, cast_fn, free_fn;

/* === Runtime init === */
void runtime_init() {
    print.tag = VAL_FUNCTION;   print.as_fn   = builtin_print;
    delay.tag = VAL_FUNCTION;   delay.as_fn   = builtin_delay;
    range_fn.tag = VAL_FUNCTION; range_fn.as_fn = builtin_range;
    subS.tag = VAL_FUNCTION;    subS.as_fn    = builtin_subS;
    subL.tag = VAL_FUNCTION;    subL.as_fn    = builtin_subL;
    cast_fn.tag = VAL_FUNCTION; cast_fn.as_fn = builtin_cast;
    free_fn.tag = VAL_FUNCTION; free_fn.as_fn = builtin_free;
}
