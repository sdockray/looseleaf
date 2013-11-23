# Break apart a page into columns of text

import cv2
import numpy as np
from scipy.cluster.vq import kmeans, vq

def invert(im):
    return 255-im

def denoise(im, ksize=3):
    return cv2.medianBlur(im, ksize)

def grey(im):
    # might be better called "red"
    if len(im.shape) > 2:
        im = im.mean(axis=2).astype(np.uint8)
    return im

def adaptive_thresh(im):
    return cv2.adaptiveThreshold(im, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)

def thresh(im, cutoff=30):
    return (255 * (im > cutoff)).astype(np.uint8)

def dilate(im, iterations=5):
    return cv2.dilate(im, None, iterations=iterations)

def smooth(im, shape=(40,10)):#, cutoff=10):
    im = cv2.blur(im, shape)
    return thresh(im)#, cutoff=cutoff)

def contours(im):
    # c, _hierarchy = cv2.findContours(im, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    c, _hierarchy = cv2.findContours(im, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    return c

def wrap_contours(contours):
    return [cv2.minAreaRect(X) for X in contours]

def normalize_rect(rect):
    ((cx, cy), (w, h), rot) = rect
    if rot < -45 and w < h:
        return ((cx,cy), (h,w), rot+90)
    else:
        return rect

# XXX: these should be percentages of the image size
def prune_rects(rects, min_width=200, max_height=200, max_width=2000):
    return filter(lambda X: X[1][0] > min_width and X[1][1] < max_height and X[1][0] < max_width, rects)

def draw_rects(im, rects, color=(0,0,255), thickness=3):
    for r in rects:
        box = np.int32(cv2.cv.BoxPoints(r)).reshape((-1,1,2))
        cv2.drawContours(im, [box], 0, color, thickness)

def multicluster_columns(rects, min_clusters=1, max_clusters=20):
    # Assumes rects have been normalized
    # XXX: assume rotation is negligible

    # Our feature vector is (cx, cy, w)
    # features = np.array([(X[0][0], X[0][1], X[1][0]) for X in rects])
    # features = np.array([(X[0][0], X[1][0]) for X in rects])
    # features = np.array([(X[0][1], X[1][0]) for X in rects])
    # features = np.array([X[1] for X in rects])

    # x1, x2
    # features = np.array([(X[0][0] - X[1][0]/2, X[0][0] + X[1][0]/2) for X in rects])

    # x1,x2,cy
    features = np.array([(X[0][0] - X[1][0]/2, X[0][0] + X[1][0]/2, X[0][1]) for X in rects])

    res = []

    for k in range(min_clusters, max_clusters): # XXX: not inclusive
        codebook, distortion = kmeans(features, k)
        clusters, distance = vq(features, codebook)

        print "For K=%d, distortion is %f and sum distance is %f" % (k, distortion, sum(distance))

        res.append({"codebook": codebook,
                    "distortion": distortion,
                    "clusters": clusters,
                    "distance": distance})
    return res

def random_color():
    return (255*np.random.random(3)).astype(np.uint8).tolist()

def draw_clusters(im, rects, clusters):
    nclusters = clusters.max() + 1
    colors = [random_color() for _X in range(nclusters)]
    for idx in range(nclusters):
        cluster_rects = np.array(rects)[clusters==idx]
        cluster_rects = [tuple(x) for x in cluster_rects]
        draw_rects(im, cluster_rects, color=colors[idx])

def merge_boxes(boxes):
    if len(boxes) == 0:
        return []
    boundings = np.array(boxes)
    return (boundings[:,0].min(), boundings[:,1].min(), 
            boundings[:,2].max(), boundings[:,3].max())

def bound_rects(rects):
    def getPoints(X):
        return [X[0][0] - X[1][0]/2,
                X[0][1] - X[1][1]/2,
                X[0][0] + X[1][0]/2,
                X[0][1] + X[1][1]/2]
    return merge_boxes([getPoints(X) for X in rects])

def draw_boxes(im, boxes):
    for box in boxes:
        cv2.drawContours(im, [np.int32(box).reshape((-1,1,2))], 0, random_color(), 4)

def prune_clusters(rects, clusters, min_lines=3):
    good_indices = np.zeros(len(clusters), dtype=np.bool)
    for c_idx in set(clusters.tolist()):
        if sum(clusters == c_idx) >= min_lines:
            good_indices[clusters == c_idx] = True

    good_rects = np.array(rects)[good_indices].tolist()
    good_clusters = clusters[good_indices]
    return (good_rects, good_clusters)
    

def bound_clusters(rects, clusters):
    return [bound_rects(np.array(rects)[clusters == X]) for X in set(clusters.tolist())]

def join_boxes(boxes, x_eps=50, y_eps=150, w_eps=50):
    for box1 in boxes:
        for box2 in boxes:
            if box1 == box2:
                continue
            # Check distance between b1x1 and b2x1, as well as b1y2 and b2y1 adn the respective widths
            b1w = box1[2]-box1[0]
            b2w = box2[2]-box2[0]
            if abs(box1[0] - box2[0]) < x_eps and abs(box1[3] - box2[1]) < y_eps and abs(b1w - b2w) < w_eps:
                box3 = merge_boxes([box1, box2])
                # Python lacks tail-recursion, duh!
                return join_boxes(filter(lambda x: x != box1 and x != box2, boxes) + [box3], 
                                  x_eps=x_eps, y_eps=y_eps, w_eps=w_eps)
    # Done!
    return boxes

def prune_boxes(boxes):
    # another stupid pruning that looks for boxes in boxes
    hitlist = []
    outboxes = list(boxes)
    for box1 in boxes:
        for box2 in boxes:
            if box1 == box2:
                continue
            # is box2 in box1?
            if box2[0] > box1[0] and box2[1] > box1[1] and box2[2] < box1[2] and box2[3] < box1[3]:
                # it is!
                if box2 in outboxes:
                    # n^3!
                    outboxes.remove(box2)
    return outboxes
            

def find_columns(path_to_image):
    im = cv2.imread(path_to_image, 0) # greyscale
    thresholded = invert(adaptive_thresh(denoise(im)))
    smoothed = smooth(thresholded)
    sm_ret = smoothed.copy()
    lines = wrap_contours(contours(smoothed))
    lines = [normalize_rect(X) for X in lines]
    lines = prune_rects(lines, min_width=im.shape[1]/5, max_width=0.9*im.shape[1])

    cluster_options = multicluster_columns(lines)
    clusters = cluster_options[-1]["clusters"]

    # lines, clusters = prune_clusters(lines, clusters)

    # Make an image that shows what's happening
    p_im = np.zeros((im.shape[0],im.shape[1],3), dtype=np.uint8)
    # Fill on all color channels
    p_im[:] = im.reshape((im.shape[0],im.shape[1],1))
    draw_clusters(p_im, lines, clusters)

    boxes = bound_clusters(lines, clusters)
    boxes = join_boxes(boxes)

    boxes = prune_boxes(boxes)

    draw_boxes(p_im, boxes)

    return im, thresholded, sm_ret, p_im, boxes

# draw_rects(d2, wrap_contours(contours((smooth(invert(thresh(im4)), shape=(40,10), cutoff=30)))))
