def find_diffs(patches):
    for I in re.finditer(
            (r"^(?:diff --git a/(.+?) b/(.+?)\nindex ([0-9a-f]+)\.\.([0-9a-f]+) [0-9]+)|"
             r"(?:diff --git a/(.+?) b/(.+?)\ndeleted file mode [0-9]+\nindex ([0-9a-f]+)\.\.([0-9a-f]+))|"
             r"(?:diff --git a/(.+?) b/(.+?)\nnew file mode [0-9]+\nindex ([0-9a-f]+)\.\.([0-9a-f]+)$)"
             "$"),
            patches, re.MULTILINE):
        g = I.groups()
        if g[0] is not None:
            yield g[0:4]
        elif g[4] is not None:
            yield g[4:8]
        elif g[8] is not None:
            yield g[8:12]
        else:
            print(I.groups())

    for I in find_diffs(patches):
        afn, bfn, ablob, bblob = I
        print(I)
            if blobs[0] == "0"*len(blobs[0]):
                continue